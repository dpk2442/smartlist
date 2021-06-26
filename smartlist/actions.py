import configparser
import datetime
import logging
import urllib.parse
import secrets

import aiohttp
import aiohttp.web

import smartlist.session


logger = logging.getLogger(__name__)


def get_home(session: smartlist.session.Session, artists_route: str):
    if session.user_info is not None:
        return aiohttp.web.HTTPTemporaryRedirect(artists_route)


def login(
        config: configparser.ConfigParser,
        session: smartlist.session.Session,
        login_callback_route: str):
    state = secrets.token_urlsafe()
    session.auth_state = state
    return aiohttp.web.HTTPTemporaryRedirect(
        "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(dict(
            client_id=config.get("auth", "client_id"),
            response_type="code",
            redirect_uri=urllib.parse.urljoin(
                config.get("auth", "callback_base_url"), login_callback_route),
            state=state,
            scope="",
        )),
    )


async def login_callback(
        config: configparser.ConfigParser,
        session: smartlist.session.Session,
        home_route: str, artists_route: str,
        login_callback_route: str,
        state: str, error: str, code: str):
    session_state = session.auth_state
    del session.auth_state
    if state != session_state:
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

        now = datetime.datetime.utcnow()
        now += datetime.timedelta(seconds=auth_data["expires_in"])
        session.user_info = dict(
            user_id=profile_data["uri"],
            access_token=auth_data["access_token"],
            access_token_expiry="{}Z".format(now.isoformat()),
        )

        return aiohttp.web.HTTPTemporaryRedirect(artists_route)


def logout(session: smartlist.session.Session, home_route: str):
    del session.user_info
    return aiohttp.web.HTTPTemporaryRedirect(home_route)
