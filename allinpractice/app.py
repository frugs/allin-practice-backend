"""This is the single sign-on app"""
import json

import flask
import flask_oauthlib.client
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
    "Grandmaster",
]
RACE_DB_KEYS = {
    "Terran": "terran_player",
    "Protoss": "protoss_player",
    "Zerg": "zerg_player",
    "Random": "random_player",
}
RACES = list(RACE_DB_KEYS.keys())
DAYS_OF_THE_WEEK = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

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


def refresh_discord_token_and_get_user_data():
    access_token = allinsso.refresh_discord_token(discord, flask.session)

    if not access_token:
        return None

    resp = discord.get(
        "users/@me", headers=discord_auth_headers(access_token), token=access_token
    )
    if resp.status != 200 or not resp.data or "id" not in resp.data:
        return None

    discord_data = resp.data
    if "id" not in discord_data:
        return None

    return discord_data


def forbidden(description=""):
    flask.abort(403, description=description)


@app.route("/member")
def login():
    discord_data = refresh_discord_token_and_get_user_data()
    if not discord_data:
        return forbidden()

    discord_id = discord_data["id"]

    if "avatar" in discord_data:
        discord_avatar = "https://cdn.discordapp.com/avatars/{}/{}".format(
            discord_id, discord_data["avatar"]
        )
    else:
        discord_avatar = ""

    discord_username = discord_data.get("username", "")
    if not discord_username:
        print("Failed to fetch discord username for user: " + discord_id)

    db = firebase_admin.db.reference()
    member_data = db.child("members").child(discord_id).get()
    member_data = member_data if member_data else {}

    db_name = member_data.get("discord_server_nick", "")
    if not db_name:
        db_name = member_data.get("discord_username", "")
    league_id = member_data.get("current_league", None)

    practice = member_data.get("practice", {})
    if not practice:
        races = [
            race for race, key in RACE_DB_KEYS.items() if member_data.get(key, False)
        ]

        practice = {"practiceRaces": races}

    result = {
        "avatar": discord_avatar,
        "player": db_name if db_name else discord_username,
        **({"league": LEAGUE_NAMES[league_id]} if league_id is not None else {}),
        "practice": practice,
    }
    return flask.jsonify(result)


@app.route("/member-practice", methods=["POST"])
def member_practice():
    if not flask.request.is_json:
        return flask.abort(400)
    data = flask.request.json

    discord_data = refresh_discord_token_and_get_user_data()
    if not discord_data:
        return forbidden()

    discord_id = discord_data["id"]
    discord_username = discord_data["username"]
    if "avatar" in discord_data:
        discord_avatar = "https://cdn.discordapp.com/avatars/{}/{}".format(
            discord_id, discord_data["avatar"]
        )
    else:
        discord_avatar = None

    player_name = data.get("player", None)
    if not player_name:
        player_name = discord_username

    practice_races = [race for race in RACES if race in data.get("practiceRaces", [])]
    timezone = data.get("timezone", None)
    week_time_ranges = {}
    for day in DAYS_OF_THE_WEEK:
        key = "timeRanges" + day
        if key not in data:
            week_time_ranges[key] = []

        week_time_ranges[key] = [
            {
                **({"from": timeRange["from"]} if "from" in timeRange else {}),
                **({"to": timeRange["to"]} if "to" in timeRange else {}),
            }
            for timeRange in data[key]
        ]

    update = {
        "practiceRaces": practice_races,
        **({"timezone": timezone} if timezone else {}),
        "player": player_name,
        **({"avatar": discord_avatar} if discord_avatar else {}),
        **week_time_ranges,
    }
    db = firebase_admin.db.reference()
    db.child("members").child(discord_id).child("practice").update(update)

    return {}
