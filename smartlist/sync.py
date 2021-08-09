import logging
import operator
import typing

import aiohttp.web

import smartlist.client
import smartlist.db
import smartlist.session


logger = logging.getLogger(__name__)


async def sync_artists(ws: aiohttp.web.WebSocketResponse,
                       db: smartlist.db.SmartListDB,
                       user_id: str,
                       spotify_client: smartlist.client.SpotifyClient):
    logger.info("Syncing artists for {}".format(user_id))
    await ws.send_json(dict(type="start",))
    artists = db.get_artists(user_id)
    for artist in artists:
        await sync_artist(ws, db, user_id, spotify_client, artist)


async def sync_artist(ws: aiohttp.web.WebSocketResponse,
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
