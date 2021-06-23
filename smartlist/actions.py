import configparser
import logging
import urllib.parse

import aiohttp
import aiohttp.web


logger = logging.getLogger(__name__)


def login(config: configparser.ConfigParser, login_callback_route: str):
    return aiohttp.web.HTTPTemporaryRedirect(
        "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(dict(
            client_id=config.get("auth", "client_id"),
            response_type="code",
            redirect_uri=urllib.parse.urljoin(
                config.get("auth", "callback_base_url"), login_callback_route),
            state="test",
            scope="",
        )),
    )


async def login_callback(
        config: configparser.ConfigParser,
        home_route: str, login_callback_route: str,
        state: str, error: str, code: str):
    if state != "test":
        logger.error("Invalid state found")
        return aiohttp.web.HTTPTemporaryRedirect(home_route)

    if error is not None:
        logger.error("Authentication request failed")
        return aiohttp.web.HTTPTemporaryRedirect(home_route)

    if code is None:
        logger.error("Code not present")
        return aiohttp.web.HTTPTemporaryRedirect(home_route)

    async with aiohttp.ClientSession() as client_session:
        token_parameters = dict(
            grant_type="authorization_code",
            client_id=config.get("auth", "client_id"),
            client_secret=config.get("auth", "client_secret"),
            code=code,
            redirect_uri=urllib.parse.urljoin(
                config.get("auth", "callback_base_url"), login_callback_route),
        )
        async with client_session.post(
                "https://accounts.spotify.com/api/token", data=token_parameters) as resp:
            if resp.status != 200:
                logger.error("Error getting token, received status {}".format(resp.status))
                return aiohttp.web.HTTPTemporaryRedirect(home_route)

            auth_data = await resp.json()

        headers = dict(
            Authorization="Bearer " + auth_data["access_token"],
        )
        async with client_session.get("https://api.spotify.com/v1/me", headers=headers) as resp:
            if resp.status != 200:
                logger.error("Error getting profile, received status {}".format(resp.status))
                return aiohttp.web.HTTPTemporaryRedirect(home_route)

            profile_data = await resp.json()

        return aiohttp.web.json_response(dict(
            auth_data=auth_data,
            profile_data=profile_data,
        ))
