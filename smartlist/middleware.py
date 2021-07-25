import typing

import aiohttp.web

import smartlist.client
import smartlist.session


@aiohttp.web.middleware
async def load_session(request: aiohttp.web.Request, handler: typing.Callable):
    request["session"] = await smartlist.session.get_session(request)
    return await handler(request)


@aiohttp.web.middleware
async def inject_client(request: aiohttp.web.Request, handler: typing.Callable):
    session = await smartlist.session.get_session(request)
    client = smartlist.client.SpotifyClient(request.app["config"], request.app["db"], session)
    request["client"] = client

    try:
        return await handler(request)
    finally:
        await client.close()
