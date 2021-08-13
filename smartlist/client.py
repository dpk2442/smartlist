import configparser
import contextlib
import datetime
import logging
import typing

import aiohttp

import smartlist.db
import smartlist.session


ARTIST_IDS_BATCH_SIZE = 50
PLAYLIST_ITEMS_BATCH_SIZE = 100
logger = logging.getLogger(__name__)


class Artist(object):

    __slots__ = ("name", "uri")
    name: str
    uri: str

    def __init__(self, name, uri):
        self.name = name
        self.uri = uri

    @classmethod
    def parse(cls, raw_artist: dict):
        return cls(
            raw_artist["name"],
            raw_artist["uri"],
        )


class Album(object):

    __slots__ = ("name", "_release_date", "_release_date_precision", "uri", "artists", "tracks")
    name: str
    _release_date: str
    _release_date_precision: str
    uri: str
    artists: typing.List[Artist]
    tracks: typing.Dict[str, "Track"]

    def __init__(self, name, release_date, release_date_precision, uri, artists):
        self.name = name
        self._release_date = release_date
        self._release_date_precision = release_date_precision
        self.uri = uri
        self.artists = artists
        self.tracks = dict()

    @property
    def release_date(self) -> datetime.datetime:
        if self._release_date_precision == "day":
            return datetime.datetime.strptime(self._release_date, "%Y-%m-%d")

        if self._release_date_precision == "month":
            return datetime.datetime.strptime(self._release_date, "%Y-%m")

        if self._release_date_precision == "year":
            return datetime.datetime.strptime(self._release_date, "%Y")

        raise ValueError("Unknown release date precision")

    def add_track(self, track: "Track"):
        if track.uri in self.tracks:
            return

        self.tracks[track.uri] = track

    @classmethod
    def parse(cls, raw_album: typing.Dict[str, typing.Any]):
        album = cls(
            raw_album["name"],
            raw_album["release_date"],
            raw_album["release_date_precision"],
            raw_album["uri"],
            [Artist.parse(raw_artist) for raw_artist in raw_album["artists"]],
        )

        if "tracks" in raw_album:
            for raw_track in raw_album["tracks"]["items"]:
                album.add_track(Track.parse(album, raw_track))

        return album


class Track(object):

    __slots__ = ("name", "uri", "disc_number", "track_number", "artists", "album")
    name: str
    uri: str
    disc_number: int
    track_number: int
    artists: typing.List[Artist]
    album: Album

    def __init__(self, name, uri, disc_number, track_number, artists, album):
        self.name = name
        self.uri = uri
        self.disc_number = disc_number
        self.track_number = track_number
        self.artists = artists
        self.album = album

    @classmethod
    def parse(cls, album: Album, raw_track: typing.Dict[str, typing.Any]):
        return cls(
            raw_track["name"],
            raw_track["uri"],
            raw_track["disc_number"],
            raw_track["track_number"],
            [Artist.parse(raw_artist) for raw_artist in raw_track["artists"]],
            album,
        )


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
    async def _make_api_call(self, method: str, url: str, body=None):
        if self._is_access_token_expired():
            await self._refresh_token()

        headers = dict(
            Authorization="Bearer {}".format(self._request_session.access_token),
        )

        async with self._get_client_session().request(
                method, url, headers=headers, json=body) as resp:
            if resp.status != 401:
                yield resp
            else:
                await self._refresh_token()
                headers["Authorization"] = "Bearer {}".format(self._request_session.access_token)
                async with self._get_client_session().request(
                        method, url, headers=headers, json=body) as resp:
                    yield resp

    async def close(self):
        if self._client_session is not None:
            await self._client_session.close()

    async def get_followed_artists(self):
        url = "https://api.spotify.com/v1/me/following?type=artist&limit=50"
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

    async def get_saved_albums(self) -> typing.List[Album]:
        url = "https://api.spotify.com/v1/me/albums?limit=50"
        albums = []
        while True:
            async with self._make_api_call("get", url) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error("Error getting saved albums: {} -> {}".format(resp.status, text))
                    raise SpotifyApiException("Error getting saved albums")

                payload = await resp.json()
                for saved_album in payload["items"]:
                    albums.append(Album.parse(saved_album["album"]))
                if not payload["next"]:
                    break

                url = payload["next"]

        return albums

    async def get_saved_tracks(self) -> typing.List[Album]:
        url = "https://api.spotify.com/v1/me/tracks?limit=50"
        albums: typing.Dict[str, Album] = dict()
        while True:
            async with self._make_api_call("get", url) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error("Error getting saved tracks: {} -> {}".format(resp.status, text))
                    raise SpotifyApiException("Error getting saved tracks")

                payload = await resp.json()
                for saved_track in payload["items"]:
                    album_uri = saved_track["track"]["album"]["uri"]
                    if album_uri not in albums:
                        albums[album_uri] = Album.parse(saved_track["track"]["album"])
                    albums[album_uri].add_track(Track.parse(
                        albums[album_uri], saved_track["track"]))

                if not payload["next"]:
                    break

                url = payload["next"]

        return list(albums.values())

    async def get_playlist(self, playlist_id: str) -> dict:
        async with self._make_api_call(
            "get",
            "https://api.spotify.com/v1/playlists/{}".format(
                playlist_id[len("spotify:playlist:"):],
            ),
        ) as resp:
            if resp.status != 200:
                logger.error("Error getting playlist: {}".format(resp.status))
                raise SpotifyApiException("Error getting playlist")

            return await resp.json()

    async def create_playlist(self, user_id: str, name: str, description: str) -> str:
        request_payload = dict(
            name=name,
            public=False,
            collaborative=False,
            description=description,
        )
        async with self._make_api_call(
                "post",
                "https://api.spotify.com/v1/users/{}/playlists".format(
                    user_id[len("spotify:user:"):]),
                body=request_payload,
        ) as resp:
            if resp.status != 201:
                text = await resp.text()
                logger.error("Error creating playlist: {} -> {}".format(resp.status, text))
                raise SpotifyApiException("Error creating playlist")

            return await resp.json()

    async def clear_playlist(self, playlist_id: str):
        async with self._make_api_call(
            "put",
            "https://api.spotify.com/v1/playlists/{}/tracks".format(
                playlist_id[len("spotify:playlist:"):]),
            body=dict(uris=[]),
        ) as resp:
            if resp.status != 201:
                text = await resp.text()
                logger.error("Error clearing playlist: {} -> {}".format(resp.status, text))
                raise SpotifyApiException("Error clearing playlist")

    async def add_items_to_playlist(self, playlist_id: str, items: typing.List[Track]):
        for batch_start in range(0, len(items), PLAYLIST_ITEMS_BATCH_SIZE):
            async with self._make_api_call(
                "post",
                "https://api.spotify.com/v1/playlists/{}/tracks".format(
                    playlist_id[len("spotify:playlist:"):]),
                body=dict(
                    uris=[i.uri for i in
                          items[batch_start: batch_start + PLAYLIST_ITEMS_BATCH_SIZE]]
                ),
            ) as resp:
                if resp.status != 201:
                    text = await resp.text()
                    logger.error("Error adding items to playlist: {} -> {}".format(
                        resp.status, text))
                    raise SpotifyApiException("Error adding items to playlist")
