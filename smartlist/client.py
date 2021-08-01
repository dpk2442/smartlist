import configparser
import contextlib
import datetime
import logging
import typing

import aiohttp

import smartlist.db
import smartlist.session


ARTIST_IDS_BATCH_SIZE = 50
logger = logging.getLogger(__name__)


class SpotifyAuthorizationException(Exception):

    def __init__(self, message):
        super().__init__(message)


class SpotifyApiException(Exception):

    def __init__(self, message):
        super().__init__(message)


class SpotifyClient(object):

    def __init__(self,
                 config: configparser.ConfigParser,
                 db: smartlist.db.SmartListDB,
                 session: smartlist.session.Session):
        self._request_session = session
        self._config = config
        self._db = db
        self._client_session = None

    def _get_client_session(self) -> aiohttp.ClientSession:
        if self._client_session is None:
            self._client_session = aiohttp.ClientSession()

        return self._client_session

    def _is_access_token_expired(self):
        expiry_time = datetime.datetime.fromisoformat(self._request_session.access_token_expiry)
        now = datetime.datetime.now(datetime.timezone.utc)
        return expiry_time - now < datetime.timedelta(minutes=5)

    async def _refresh_token(self):
        logger.info("Attempting to refresh token for {}".format(self._request_session.user_id))
        async with self._get_client_session().post(
                "https://accounts.spotify.com/api/token",
                data=dict(
                    grant_type="refresh_token",
                    refresh_token=self._db.get_refresh_token(self._request_session.user_id),
                    client_id=self._config.get("auth", "client_id"),
                    client_secret=self._config.get("auth", "client_secret"),
                )
        ) as resp:
            if resp.status != 200:
                logger.error("Failed to refresh token for {}".format(self._request_session.user_id))
                raise SpotifyAuthorizationException(
                    "Unable to refresh token, status code {}".format(resp.status))

            payload = await resp.json()
            if "refresh_token" in payload:
                self._db.upsert_user(self._request_session.user_id, payload["refresh_token"])

            now = datetime.datetime.now(datetime.timezone.utc)
            now += datetime.timedelta(seconds=payload["expires_in"])
            self._request_session.user_info = dict(
                user_id=self._request_session.user_id,
                access_token=payload["access_token"],
                access_token_expiry=now.isoformat(),
            )

        logger.info("Successfully refreshed token for {}".format(self._request_session.user_id))

    @contextlib.asynccontextmanager
    async def _make_api_call(self, method: str, url: str):
        if self._is_access_token_expired():
            await self._refresh_token()

        headers = dict(
            Authorization="Bearer {}".format(self._request_session.access_token),
        )

        async with self._get_client_session().request(method, url, headers=headers) as resp:
            if resp.status != 401:
                yield resp
            else:
                await self._refresh_token()
                headers["Authorization"] = "Bearer {}".format(self._request_session.access_token)
                async with self._get_client_session().request(method, url, headers=headers) as resp:
                    yield resp

    async def close(self):
        if self._client_session is not None:
            await self._client_session.close()

    async def get_followed_artists(self):
        url = "https://api.spotify.com/v1/me/following?type=artist&limit=10"
        artists = []
        while True:
            async with self._make_api_call("get", url) as resp:
                if resp.status != 200:
                    raise SpotifyApiException("Error getting artists")

                payload = await resp.json()
                artists.extend(payload["artists"]["items"])
                if not payload["artists"]["next"]:
                    break

                url = payload["artists"]["next"]

        artists.sort(key=lambda a: a["name"].lower())
        return artists

    async def get_artists_by_ids(self, artist_ids: typing.List[str]):
        artists = []
        for batch_start in range(0, len(artist_ids), ARTIST_IDS_BATCH_SIZE):
            async with self._make_api_call(
                "get",
                "https://api.spotify.com/v1/artists?ids={}".format(
                    ",".join(id[len("spotify:artist:"):] for id in
                             artist_ids[batch_start:batch_start + ARTIST_IDS_BATCH_SIZE])),
            ) as resp:
                if resp.status != 200:
                    print(await resp.text())
                    raise SpotifyApiException("Error getting artists by id")

                payload = await resp.json()
                artists.extend(payload["artists"])

        artists.sort(key=lambda a: a["name"].lower())
        return artists
