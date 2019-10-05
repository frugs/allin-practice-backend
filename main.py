import werkzeug.wrappers
from werkzeug.serving import run_simple
from werkzeug.wsgi import DispatcherMiddleware

from allinsso import app as sso_app
from allinpractice import app as practice_app

NOT_FOUND = werkzeug.wrappers.Response("Nothing to see here!", status=404)


def main():
    run_simple(
        "localhost",
        5001,
        DispatcherMiddleware(
            NOT_FOUND, {"/practice_backend": practice_app, "/sso": sso_app}
        ),
        threaded=True,
        ssl_context="adhoc",
    )


if __name__ == "__main__":
    main()
