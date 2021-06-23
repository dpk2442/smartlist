import configparser
import logging
import os

import aiohttp
import aiohttp_jinja2
import jinja2

import smartlist.handlers


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


def main():
    init_logging()

    script_dir = os.path.dirname(os.path.realpath(__file__))
    root_path = os.path.realpath(os.path.join(script_dir, ".."))

    config = configparser.ConfigParser()
    files_read = config.read(os.path.realpath(os.path.join(root_path, "config.ini")))
    if (len(files_read) == 0):
        logger.error("No config file found")
        os.exit(1)
    else:
        logger.info("Loaded config from {}".format(",".join(files_read)))

    template_path = os.path.realpath(os.path.join(root_path, "templates"))

    app = aiohttp.web.Application()
    app["config"] = config
    app.router.add_routes(smartlist.handlers.routes)

    aiohttp_jinja2.setup(
        app,
        loader=jinja2.FileSystemLoader(template_path))

    host = config.get("web", "host", fallback="127.0.0.1")
    port = config.getint("web", "port", fallback=7578)
    logger.info("Starting server on {}:{}".format(host, port))
    aiohttp.web.run_app(app, host=host, port=port,
                        print=lambda *args, **kwargs: None)
