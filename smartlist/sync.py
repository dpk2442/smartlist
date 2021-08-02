import asyncio

import aiohttp.web

import smartlist.client
import smartlist.db
import smartlist.session


async def sync_artists(ws: aiohttp.web.WebSocketResponse,
                       db: smartlist.db.SmartListDB,
                       user_id: str,
                       spotify_client: smartlist.client.SpotifyClient):
    await ws.send_json(dict(type="start",))
    artists = db.get_artists(user_id)
    for artist in artists:
        await sync_artist(ws, db, user_id, spotify_client, artist)


async def sync_artist(ws: aiohttp.web.WebSocketResponse,
                      db: smartlist.db.SmartListDB,
                      user_id: str,
                      spotify_client: smartlist.client.SpotifyClient,
                      artist: dict):
    await ws.send_json(dict(
        type="artistStart",
        artistId=artist["id"],
    ))
    await asyncio.sleep(1)
    await ws.send_json(dict(
        type="artistComplete",
        artistId=artist["id"],
    ))
