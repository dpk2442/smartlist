import configparser
import datetime
import logging
import operator
import typing

import aiohttp.web

import smartlist.client
import smartlist.db
import smartlist.session


logger = logging.getLogger(__name__)


async def sync_artists(ws: aiohttp.web.WebSocketResponse,
                       config: configparser.ConfigParser,
                       db: smartlist.db.SmartListDB,
                       user_id: str,
                       spotify_client: smartlist.client.SpotifyClient):
    logger.info("Syncing artists for {}".format(user_id))
    await ws.send_json(dict(type="start",))
    artists = db.get_artists(user_id)
    for artist in artists:
        await sync_artist(ws, config, db, user_id, spotify_client, artist)


async def sync_artist(ws: aiohttp.web.WebSocketResponse,
                      config: configparser.ConfigParser,
                      db: smartlist.db.SmartListDB,
                      user_id: str,
                      spotify_client: smartlist.client.SpotifyClient,
                      artist: dict):
    logger.info("Syncing artist {}".format(artist["id"]))
    await ws.send_json(dict(
        type="artistStart",
        artistId=artist["id"],
    ))

    try:
        saved_albums = await spotify_client.get_saved_albums()
        saved_albums = filter_albums(artist["id"], saved_albums)

        saved_tracks = await spotify_client.get_saved_tracks()
        saved_tracks = filter_albums(artist["id"], saved_tracks)

        all_saved_albums = merge_album_lists(saved_albums, saved_tracks)
        final_track_list = convert_album_list_to_track_list(all_saved_albums)

        logger.info("Final track list: {}".format(", ".join(t.name for t in final_track_list)))

        playlist_id = await get_or_create_playlist(config, user_id, spotify_client, artist)
        last_updated = update_artist_playlist_info(db, user_id, artist, playlist_id)
    except Exception:
        logger.exception("Failed syncing artist {}".format(artist["id"]))
        await ws.send_json(dict(
            type="artistError",
            artistId=artist["id"],
            error="Unable to sync"
        ))
        return

    logger.info("Finished syncing artist {}".format(artist["id"]))
    await ws.send_json(dict(
        type="artistComplete",
        artistId=artist["id"],
        lastUpdated=last_updated.isoformat(),
    ))


def filter_albums(artist_id: str, albums: typing.List[smartlist.client.Album]) \
        -> typing.List[smartlist.client.Album]:
    filtered_albums = []
    for album in albums:
        for track in list(album.tracks.values()):
            if not any(map(
                lambda track_artist: track_artist.uri == artist_id,
                track.artists,
            )):
                del album.tracks[track.uri]

        if len(album.tracks) > 0:
            filtered_albums.append(album)

    return filtered_albums


def merge_album_lists(*album_lists: typing.List[smartlist.client.Album]) \
        -> typing.List[smartlist.client.Album]:
    merged_album_dict: typing.Dict[str, smartlist.client.Album] = dict()
    for album_list in album_lists:
        for album in album_list:
            if album.uri not in merged_album_dict:
                merged_album_dict[album.uri] = album
            else:
                for track in album.tracks.values():
                    merged_album_dict[album.uri].add_track(track)

    return list(merged_album_dict.values())


def convert_album_list_to_track_list(album_list: typing.List[smartlist.client.Album]) \
        -> typing.List[smartlist.client.Track]:
    track_list = []
    for album in sorted(album_list, key=operator.attrgetter("release_date")):
        for track in sorted(
                sorted(album.tracks.values(),
                       key=operator.attrgetter("track_number")),
                key=operator.attrgetter("disc_number")):
            track_list.append(track)

    return track_list


async def get_or_create_playlist(config: configparser.ConfigParser,
                                 user_id: str,
                                 spotify_client: smartlist.client.SpotifyClient,
                                 artist: dict):
    if artist["playlist_id"] is not None:
        try:
            await spotify_client.get_playlist(artist["playlist_id"])
            return artist["playlist_id"]
        except smartlist.client.SpotifyApiException:
            logger.error("Could not retrieve playlist, constructing new one")

    logger.info("No playlist found for artist {}, creating a new one".format(artist["id"]))
    [artist] = await spotify_client.get_artists_by_ids([artist["id"]])

    name_template = config.get("playlist", "name_template", fallback="SmartList: {name}")
    playlist_name = name_template.format(**artist)

    description_template = config.get(
        "playlist", "description_template",
        fallback="An automatic playlist for \"{name}\" created by SmartList")
    playlist_description = description_template.format(**artist)

    playlist = await spotify_client.create_playlist(user_id, playlist_name, playlist_description)
    return playlist["uri"]


def update_artist_playlist_info(db: smartlist.db.SmartListDB,
                                user_id: str,
                                artist: dict,
                                playlist_id: str):
    now = datetime.datetime.now(datetime.timezone.utc)
    db.update_artist_playlist(user_id, artist["id"], playlist_id, now.isoformat())
    return now
