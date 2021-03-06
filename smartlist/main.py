import base64
import configparser
import logging
import os
import sys

import aiohttp
import aiohttp.web
import aiohttp_jinja2
import aiohttp_session
import aiohttp_session.cookie_storage
import jinja2

import smartlist.db
import smartlist.handlers
import smartlist.middleware
import smartlist.session


logger = logging.getLogger(__name__)


def init_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "{asctime} - {levelname:>8} - {name} - {message}", style="{")

    ch.setFormatter(formatter)

    root_logger.addHandler(ch)


async def load_session_context_processor(request):
    return {
        "session": request["session"],
        "flashes": request["session"].pop_flashes(),
    }


def main():
    init_logging()

    script_dir = os.path.dirname(os.path.realpath(__file__))
    root_path = os.path.realpath(os.path.join(script_dir, ".."))

    config = configparser.ConfigParser()
    files_read = config.read(os.path.realpath(os.path.join(root_path, "config.ini")))
    if (len(files_read) == 0):
        logger.error("No config file found")
        sys.exit(1)
    else:
        logger.info("Loaded config from {}".format(",".join(files_read)))

    template_path = os.path.realpath(os.path.join(root_path, "templates"))
    static_path = os.path.realpath(os.path.join(root_path, "static"))

    app = aiohttp.web.Application()
    app["config"] = config
    app["db"] = smartlist.db.init_db(root_path, config)
    app["static_root_url"] = "/assets"
    app.router.add_static(app["static_root_url"], static_path)
    app.router.add_routes(smartlist.handlers.routes)

    secret_key = base64.urlsafe_b64decode(config.get("session", "secret_key"))
    aiohttp_session.setup(app, aiohttp_session.cookie_storage.EncryptedCookieStorage(secret_key))

    app.middlewares.extend([
        smartlist.middleware.load_session,
        smartlist.middleware.inject_client,
        smartlist.middleware.generate_csrf_token,
    ])

    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(template_path),
        context_processors=[load_session_context_processor])

    host = config.get("web", "host", fallback="127.0.0.1")
    port = config.getint("web", "port", fallback=7578)
    logger.info("Starting server on {}:{}".format(host, port))
    aiohttp.web.run_app(app, host=host, port=port,
                        print=lambda *args, **kwargs: None)
