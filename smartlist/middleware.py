import typing

import aiohttp.web

import smartlist.session


@aiohttp.web.middleware
async def load_session(request: aiohttp.web.Request, handler: typing.Callable):
    request["session"] = await smartlist.session.get_session(request)
    return await handler(request)
