import aiohttp.web
import aiohttp_jinja2

import smartlist.actions
import smartlist.client
import smartlist.handler_util

routes = aiohttp.web.RouteTableDef()


@routes.get("/", name="home")
@aiohttp_jinja2.template("home.html")
def get_home(request: aiohttp.web.Request):
    return smartlist.actions.get_home(
        request["session"],
        str(request.app.router["artists"].url_for()),
    )


@routes.get("/artists", name="artists")
@smartlist.handler_util.require_auth()
@aiohttp_jinja2.template("artists.html")
async def get_artists(request: aiohttp.web.Request):
    return await smartlist.actions.get_artists(
        request.app["db"],
        request["session"],
        request["client"],
    )


@routes.get("/artists/edit", name="edit_artists")
@smartlist.handler_util.require_auth()
@aiohttp_jinja2.template("artists_edit.html")
async def get_artists_edit(request: aiohttp.web.Request):
    return await smartlist.actions.get_artists_edit(
        request.app["db"],
        request["session"],
        request["client"],
    )


@routes.post("/api/v1/artists", name="api_artists")
@smartlist.handler_util.require_auth(redirect_on_fail=False)
@smartlist.handler_util.require_csrf
async def post_artists(request: aiohttp.web.Request):
    return await smartlist.actions.post_artists(
        request.app["db"],
        request["session"],
        await smartlist.handler_util.get_json_payload(request),
    )


@routes.get("/api/v1/artists/sync", name="api_artists_sync")
@smartlist.handler_util.require_auth(redirect_on_fail=False)
async def get_artists_sync(request: aiohttp.web.Request):
    return await smartlist.actions.get_artists_sync(
        request,
        request.app["config"],
        request.app["db"],
        request["session"],
        request["client"],
    )


@routes.get("/login", name="login")
def login(request: aiohttp.web.Request):
    return smartlist.actions.login(
        request.app["config"],
        request["session"],
        str(request.app.router["login_callback"].url_for()),
    )


@routes.get("/login_callback", name="login_callback")
async def login_callback(request: aiohttp.web.Request):
    return await smartlist.actions.login_callback(
        request.app["config"],
        request.app["db"],
        request["session"],
        str(request.app.router["home"].url_for()),
        str(request.app.router["artists"].url_for()),
        str(request.app.router["login_callback"].url_for()),
        request.query.get("state", None),
        request.query.get("error", None),
        request.query.get("code", None),
    )


@routes.get("/logout", name="logout")
def logout(request: aiohttp.web.Request):
    return smartlist.actions.logout(
        request["session"],
        str(request.app.router["home"].url_for()),
    )
