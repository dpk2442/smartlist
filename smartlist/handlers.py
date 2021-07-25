import aiohttp.web
import aiohttp_jinja2

import smartlist.client
import smartlist.actions

routes = aiohttp.web.RouteTableDef()


def require_auth(func):
    async def inner(request):
        if request["session"].user_info is None:
            raise aiohttp.web.HTTPFound(request.app.router["home"].url_for())

        return await func(request)
    return inner


@routes.get("/", name="home")
@aiohttp_jinja2.template("home.html")
def get_home(request: aiohttp.web.Request):
    return smartlist.actions.get_home(
        request["session"],
        str(request.app.router["artists"].url_for()),
    )


@routes.get("/artists", name="artists")
@require_auth
async def get_artists(request: aiohttp.web.Request):
    return aiohttp.web.HTTPTemporaryRedirect(
        request.app.router["edit_artists"].url_for(),
    )


@routes.get("/artists/edit", name="edit_artists")
@require_auth
@aiohttp_jinja2.template("artists_edit.html")
async def get_artists_edit(request: aiohttp.web.Request):
    return await smartlist.actions.get_artists(
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
