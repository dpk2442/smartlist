import configparser
import datetime
import logging
import urllib.parse
import secrets

import aiohttp
import aiohttp.web

import smartlist.client
import smartlist.db
import smartlist.session


logger = logging.getLogger(__name__)


def get_home(session: smartlist.session.Session, artists_route: str):
    if session.user_info is not None:
        return aiohttp.web.HTTPTemporaryRedirect(artists_route)


async def get_artists(db: smartlist.db.SmartListDB,
                      session: smartlist.session.Session,
                      spotify_client: smartlist.client.SpotifyClient):
    return dict(
        saved_artists={artist["id"] for artist in db.get_artists(session.user_id)},
        followed_artists=await spotify_client.get_followed_artists(),
    )


async def post_artists(db: smartlist.db.SmartListDB, session: smartlist.session.Session, payload):
    if not isinstance(payload, dict) or \
            "artists" not in payload or \
            not isinstance(payload["artists"], dict):
        return aiohttp.web.HTTPBadRequest(text="Invalid request body")

    artists_to_add = []
    artists_to_remove = []
    for artist, should_save in payload["artists"].items():
        if should_save:
            artists_to_add.append(artist)
        else:
            artists_to_remove.append(artist)

    db.add_artists(session.user_id, artists_to_add)
    db.remove_artists(session.user_id, artists_to_remove)

    return aiohttp.web.json_response()


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
            scope="user-follow-read",
        )),
    )


async def login_callback(
        config: configparser.ConfigParser,
        db: smartlist.db.SmartListDB,
        session: smartlist.session.Session,
        home_route: str, artists_route: str,
        login_callback_route: str,
        state: str, error: str, code: str):
    session_state = session.auth_state
    del session.auth_state
    if state != session_state:
        logger.error("Invalid state found")
        session.add_flash(dict(type="error", msg="Encountered an error logging in."))
        return aiohttp.web.HTTPTemporaryRedirect(home_route)

    if error is not None:
        logger.error("Authentication request failed")
        session.add_flash(dict(type="error", msg="Encountered an error logging in."))
        return aiohttp.web.HTTPTemporaryRedirect(home_route)

    if code is None:
        logger.error("Code not present")
        session.add_flash(dict(type="error", msg="Encountered an error logging in."))
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
                session.add_flash(dict(type="error", msg="Encountered an error logging in."))
                return aiohttp.web.HTTPTemporaryRedirect(home_route)

            auth_data = await resp.json()

        headers = dict(
            Authorization="Bearer " + auth_data["access_token"],
        )
        async with client_session.get("https://api.spotify.com/v1/me", headers=headers) as resp:
            if resp.status != 200:
                logger.error("Error getting profile, received status {}".format(resp.status))
                session.add_flash(dict(type="error", msg="Encountered an error logging in."))
                return aiohttp.web.HTTPTemporaryRedirect(home_route)

            profile_data = await resp.json()

        now = datetime.datetime.now(datetime.timezone.utc)
        now += datetime.timedelta(seconds=auth_data["expires_in"])
        session.user_info = dict(
            user_id=profile_data["uri"],
            access_token=auth_data["access_token"],
            access_token_expiry=now.isoformat(),
        )
        db.upsert_user(profile_data["uri"], auth_data["refresh_token"])

        return aiohttp.web.HTTPTemporaryRedirect(artists_route)


def logout(session: smartlist.session.Session, home_route: str):
    del session.user_info
    return aiohttp.web.HTTPTemporaryRedirect(home_route)
