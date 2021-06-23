import aiohttp.web
import aiohttp_jinja2

import smartlist.actions

routes = aiohttp.web.RouteTableDef()


@routes.get("/", name="home")
@aiohttp_jinja2.template("home.html")
def get_home(request: aiohttp.web.Request):
    pass


@routes.get("/login", name="login")
def login(request: aiohttp.web.Request):
    return smartlist.actions.login(
        request.app["config"],
        str(request.app.router["login_callback"].url_for()),
    )


@routes.get("/login_callback", name="login_callback")
async def login_callback(request: aiohttp.web.Request):
    return await smartlist.actions.login_callback(
        request.app["config"],
        str(request.app.router["home"].url_for()),
        str(request.app.router["login_callback"].url_for()),
        request.query.get("state", None),
        request.query.get("error", None),
        request.query.get("code", None),
    )
