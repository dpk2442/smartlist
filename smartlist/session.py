import aiohttp.web
import aiohttp_session


class Session(object):

    def __init__(self, session):
        self._session = session

    def add_flash(self, flash):
        if "flash" not in self._session:
            self._session["flash"] = []

        self._session["flash"].append(flash)

    def pop_flashes(self):
        if "flash" not in self._session:
            return []

        flashes = self._session["flash"]
        del self._session["flash"]
        return flashes

    @property
    def auth_state(self):
        if "auth_state" not in self._session:
            return None

        return self._session["auth_state"]

    @auth_state.setter
    def auth_state(self, value):
        self._session["auth_state"] = value

    @auth_state.deleter
    def auth_state(self):
        if "auth_state" not in self._session:
            return

        del self._session["auth_state"]

    @property
    def user_info(self):
        if "user_info" not in self._session:
            return None

        return self._session["user_info"]

    @user_info.setter
    def user_info(self, value):
        self._session["user_info"] = value

    @user_info.deleter
    def user_info(self):
        if "user_info" not in self._session:
            return

        del self._session["user_info"]

    @property
    def user_id(self):
        if self.user_info is None or "user_id" not in self.user_info:
            return None

        return self.user_info["user_id"]

    @property
    def access_token(self):
        if self.user_info is None or "access_token" not in self.user_info:
            return None

        return self.user_info["access_token"]

    @property
    def access_token_expiry(self):
        if self.user_info is None or "access_token_expiry" not in self.user_info:
            return None

        return self.user_info["access_token_expiry"]

    def __repr__(self) -> str:  # pragma: no cover
        return repr(self._session)


async def get_session(request: aiohttp.web.Request):
    return Session(await aiohttp_session.get_session(request))
