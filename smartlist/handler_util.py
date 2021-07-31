import aiohttp.web


def require_auth(*, redirect_on_fail=True):
    def decorator(func):
        async def inner(request):
            if request["session"].user_info is None:
                if redirect_on_fail:
                    raise aiohttp.web.HTTPFound(request.app.router["home"].url_for())
                else:
                    raise aiohttp.web.HTTPUnauthorized(text="Not logged in!")

            return await func(request)
        return inner
    return decorator


def require_csrf(func):
    async def inner(request: aiohttp.web.Request):
        provided_token = request.headers.getone("X-CSRF-Token", default=None)
        if request["session"].csrf_token != provided_token:
            raise aiohttp.web.HTTPUnauthorized(text="No CSRF token provided!")

        return await func(request)
    return inner


async def get_json_payload(request: aiohttp.web.Request):
    try:
        return await request.json()
    except Exception:
        raise aiohttp.web.HTTPBadRequest(text="Could not parse request")
