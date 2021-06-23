import aiohttp.web
import aiohttp_jinja2

routes = aiohttp.web.RouteTableDef()


@routes.get("/")
@aiohttp_jinja2.template("home.html")
def get_home(request):
    pass
