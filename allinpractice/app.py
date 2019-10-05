"""This is the single sign-on app"""
import json
import os

import flask
import flask_oauthlib.client
import requests
import allinsso
import firebase_admin
import firebase_admin.db

from google.cloud import datastore

datastore_client = datastore.Client()


def retrieve_config_value(key: str) -> str:
    return datastore_client.get(datastore_client.key("Config", key))["value"]


SECRET_KEY = retrieve_config_value("cookieEncryptionKey")
DISCORD_CLIENT_KEY = retrieve_config_value("discordClientKey")
DISCORD_CLIENT_SECRET = retrieve_config_value("discordClientSecret")
FIREBASE_CONFIG = json.loads(retrieve_config_value("firebaseConfig"))

LEAGUE_NAMES = [
    "Bronze",
    "Silver",
    "Gold",
    "Platinum",
    "Diamond",
    "Master",
    "Grandmaster"
]
RACE_DB_KEYS = {
    "Terran": "terran_player",
    "Protoss": "protoss_player",
    "Zerg": "zerg_player",
    "Random": "random_player",
}

app = flask.Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True

oauth = flask_oauthlib.client.OAuth(app)

discord = allinsso.create_discord_remote_app(
    oauth, DISCORD_CLIENT_KEY, DISCORD_CLIENT_SECRET
)

firebase_admin.initialize_app(options=FIREBASE_CONFIG)


def discord_auth_headers(access_token: str) -> dict:
    return {"Authorization": "Bearer " + access_token, "User-Agent": "Mozilla/5.0"}


def forbidden(description=""):
    flask.abort(403, description=description)


@app.route("/member")
def login():
    access_token = allinsso.refresh_discord_token(discord, flask.session)

    if not access_token:
        return forbidden()

    resp = discord.get(
        "users/@me", headers=discord_auth_headers(access_token), token=access_token
    )
    if resp.status != 200 or not resp.data or "id" not in resp.data:
        return forbidden()

    discord_data = resp.data
    discord_id = discord_data["id"]

    if "avatar" in resp.data:
        discord_avatar = "https://cdn.discordapp.com/avatars/{}/{}".format(
            discord_id, discord_data["avatar"]
        )
    else:
        discord_avatar = ""

    discord_username = resp.data.get("username", "")
    if not discord_username:
        print("Failed to fetch discord username for user: " + discord_id)

    db = firebase_admin.db.reference()
    member_data = db.child("members").child(discord_id).get()
    if not member_data:
        return forbidden()

    db_name = member_data.get("discord_server_nick", "")
    if not db_name:
        db_name = member_data.get("discord_username", "")
    league_id = member_data.get("current_league", None)

    practice = member_data.get("practice", {})
    if not practice:
        races = [
            race for race, key in RACE_DB_KEYS.items() if member_data.get(key, False)
        ]

        practice = {
            "practiceRaces": races,
        }

    result = {
        "avatar": discord_avatar,
        "player": db_name if db_name else discord_username,
        **({"league": LEAGUE_NAMES[league_id]} if league_id is not None else {}),
        "practice": practice,
    }
    return flask.jsonify(result)
