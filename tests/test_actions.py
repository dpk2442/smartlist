import datetime

import pytest
import unittest.mock

import smartlist.actions
import smartlist.session


def test_get_home():
    session = smartlist.session.Session({})
    assert smartlist.actions.get_home(session, "artists_route") is None

    session.user_info = "user_info"
    resp = smartlist.actions.get_home(session, "artists_route")
    assert resp is not None
    assert resp.status == 307
    assert resp.location == "artists_route"


@pytest.mark.asyncio
async def test_get_artists():
    db = unittest.mock.Mock()
    db.get_artists.return_value = [
        dict(id="id1", playlist_id=None), dict(id="id2", playlist_id="pid2")]
    session = smartlist.session.Session({})
    session.user_info = dict(user_id="user_id")
    client = unittest.mock.AsyncMock()
    client.get_artists_by_ids.return_value = [dict(uri="id2"), dict(uri="id1")]

    resp = await smartlist.actions.get_artists(db, session, client)

    assert resp == dict(
        saved_artists=[
            dict(details=dict(uri="id2"), state=dict(id="id2", playlist_id="pid2")),
            dict(details=dict(uri="id1"), state=dict(id="id1", playlist_id=None)),
        ]
    )
    db.get_artists.assert_called_once_with("user_id")
    client.get_artists_by_ids.assert_called_once_with(["id1", "id2"])


@pytest.mark.asyncio
async def test_get_artists_edit():
    db = unittest.mock.Mock()
    db.get_artists.return_value = [dict(id="id1"), dict(id="id2")]
    session = smartlist.session.Session({})
    session.user_info = dict(user_id="user_id")
    client = unittest.mock.AsyncMock()
    client.get_followed_artists.return_value = "artists"

    resp = await smartlist.actions.get_artists_edit(db, session, client)

    assert resp == dict(
        saved_artists={"id1", "id2"},
        followed_artists="artists",
    )
    db.get_artists.assert_called_once_with("user_id")
    client.get_followed_artists.assert_called_once_with()


@pytest.mark.asyncio
class TestPostArtists(object):

    async def test_success(self):
        mock_db = unittest.mock.Mock()
        session = smartlist.session.Session({})
        session.user_info = dict(user_id="user_id")
        payload = dict(
            artists=dict(
                a1=True,
                a2=False,
                a3=True,
                a4=True,
                a5=False,
            ),
        )
        resp = await smartlist.actions.post_artists(mock_db, session, payload)

        assert resp.status == 200
        mock_db.add_artists.assert_called_once_with("user_id", ["a1", "a3", "a4"])
        mock_db.remove_artists.assert_called_once_with("user_id", ["a2", "a5"])

    @pytest.mark.parametrize("payload", [
        "string",
        [],
        dict(),
        dict(artists="string"),
    ], ids=("string", "list", "empty_dict", "invalid_artists"))
    async def test_bad_input(self, payload):
        resp = await smartlist.actions.post_artists(None, None, payload)
        assert resp.status == 400


@pytest.mark.asyncio
class TestGetArtistsSync(object):

    @pytest.fixture
    def mock_websocket(self, monkeypatch: pytest.MonkeyPatch):
        mock = unittest.mock.AsyncMock()
        mock_constructor = unittest.mock.Mock()
        mock_constructor.return_value = mock
        monkeypatch.setattr("smartlist.actions.aiohttp.web.WebSocketResponse",
                            mock_constructor)
        return mock

    @pytest.fixture
    def mock_sync(self, monkeypatch: pytest.MonkeyPatch):
        mock = unittest.mock.AsyncMock()
        monkeypatch.setattr("smartlist.actions.smartlist.sync.sync_artists",
                            mock)
        return mock

    async def test_success(self,
                           mock_websocket: unittest.mock.AsyncMock,
                           mock_sync: unittest.mock.AsyncMock):
        mock_websocket.receive_json.return_value = dict(
            type="csrf",
            csrfToken="token",
        )

        mock_session = smartlist.session.Session({})
        mock_session.user_info = dict(user_id="user_id")
        mock_session.csrf_token = "token"

        resp = await smartlist.actions.get_artists_sync(
            "request", "config", "db", mock_session, "client")

        assert resp == mock_websocket
        mock_websocket.prepare.assert_called_once_with("request")
        mock_websocket.receive_json.assert_called_once_with()
        mock_sync.assert_called_once_with(mock_websocket, "config", "db", "user_id", "client")

    async def test_recieve_json_exception(self,
                                          mock_websocket: unittest.mock.AsyncMock,
                                          mock_sync: unittest.mock.AsyncMock):
        mock_websocket.receive_json.side_effect = Exception()

        resp = await smartlist.actions.get_artists_sync(
            "request", "config", "db", "session", "client")

        assert resp.status == 401
        mock_websocket.prepare.assert_called_once_with("request")
        mock_websocket.receive_json.assert_called_once_with()
        mock_sync.assert_not_called()

    async def test_token_mismatch(self,
                                  mock_websocket: unittest.mock.AsyncMock,
                                  mock_sync: unittest.mock.AsyncMock):
        mock_websocket.receive_json.return_value = dict(
            type="csrf",
            csrfToken="wsToken",
        )

        mock_session = smartlist.session.Session({})
        mock_session.csrf_token = "sessionToken"

        resp = await smartlist.actions.get_artists_sync(
            "request", "config", "db", mock_session, "client")

        assert resp.status == 401
        mock_websocket.prepare.assert_called_once_with("request")
        mock_websocket.receive_json.assert_called_once_with()
        mock_sync.assert_not_called()


def test_login():
    config = unittest.mock.Mock()
    config.get.side_effect = ["client_id", "http://base_url"]
    session = smartlist.session.Session({})

    resp = smartlist.actions.login(config, session, "login_callback")

    assert session.auth_state is not None
    assert resp.status == 307
    assert resp.location == (
        "https://accounts.spotify.com/authorize?client_id=client_id&response_type=code&" +
        "redirect_uri=http%3A%2F%2Fbase_url%2Flogin_callback&state={}&scope={}".format(
            session.auth_state,
            ("user-follow-read+user-library-read+"
             "playlist-modify-private+playlist-modify-public"))
    )
    config.get.assert_has_calls((
        unittest.mock.call("auth", "client_id"),
        unittest.mock.call("auth", "callback_base_url"),
    ))


@pytest.mark.asyncio
class TestLoginCallback(object):

    @pytest.fixture
    def mock_session(self):
        session = smartlist.session.Session({})
        session.auth_state = "state"
        return session

    @pytest.fixture
    def mock_client_session_constructor(self, monkeypatch):
        mock = unittest.mock.MagicMock()
        mock.return_value.__aenter__.return_value.post = unittest.mock.MagicMock()
        mock.return_value.__aenter__.return_value.get = unittest.mock.MagicMock()
        monkeypatch.setattr("aiohttp.ClientSession", mock)
        return mock

    async def test_bad_state(self, mock_session):
        resp = await smartlist.actions.login_callback(
            None, None, mock_session, "home_route", "artists_route", None, None, None, None, None)
        assert resp.status == 307
        assert resp.location == "home_route"
        assert mock_session.pop_flashes() == [dict(
            type="error", msg="Encountered an error logging in.")]

    async def test_error(self, mock_session):
        resp = await smartlist.actions.login_callback(
            None, None, mock_session, "home_route", "artists_route",
            None, None, "state", "error", None)
        assert resp.status == 307
        assert resp.location == "home_route"
        assert mock_session.pop_flashes() == [dict(
            type="error", msg="Encountered an error logging in.")]

    async def test_missing_code(self, mock_session):
        resp = await smartlist.actions.login_callback(
            None, None, mock_session, "home_route", "artists_route",
            None, None, "state", None, None)
        assert resp.status == 307
        assert resp.location == "home_route"
        assert mock_session.pop_flashes() == [dict(
            type="error", msg="Encountered an error logging in.")]

    async def test_success(self, monkeypatch, mock_session, mock_client_session_constructor):
        mock_config = unittest.mock.Mock()
        mock_config.get.side_effect = ["client_id", "client_secret", "http://callback_base_url", ""]

        mock_db = unittest.mock.Mock()

        utcnow = datetime.datetime.now(datetime.timezone.utc)
        mock_datetime_datetime = unittest.mock.Mock()
        mock_datetime_datetime.now.return_value = utcnow
        monkeypatch.setattr("smartlist.actions.datetime.datetime", mock_datetime_datetime)

        mock_client_session = mock_client_session_constructor.return_value.__aenter__.return_value

        post_token_response = mock_client_session.post.return_value.__aenter__.return_value
        post_token_response.status = 200
        post_token_response.json.side_effect = (dict(
            access_token="access_token",
            expires_in=60,
            refresh_token="refresh_token",
        ),)

        get_profile_response = mock_client_session.get.return_value.__aenter__.return_value
        get_profile_response.status = 200
        get_profile_response.json.side_effect = (dict(
            uri="spotify:user:user_id",
        ),)

        resp = await smartlist.actions.login_callback(
            mock_config, mock_db, mock_session,
            "home_route", "artists_route", "login_callback_route",
            None, "state", None, "code")

        assert resp.status == 307
        assert resp.location == "artists_route"
        mock_config.get.assert_has_calls((
            unittest.mock.call("auth", "client_id"),
            unittest.mock.call("auth", "client_secret"),
            unittest.mock.call("auth", "callback_base_url"),
            unittest.mock.call("auth", "allowed_users", fallback=""),
        ))
        mock_client_session_constructor.assert_called_once_with()
        mock_client_session.post.assert_called_once_with(
            "https://accounts.spotify.com/api/token", data=dict(
                grant_type="authorization_code",
                client_id="client_id",
                client_secret="client_secret",
                code="code",
                redirect_uri="http://callback_base_url/login_callback_route",
            ))
        mock_client_session.get.assert_called_once_with(
            "https://api.spotify.com/v1/me", headers=dict(Authorization="Bearer access_token")
        )
        post_token_response.json.assert_called_once_with()
        get_profile_response.json.assert_called_once_with()

        expiry = utcnow + datetime.timedelta(seconds=60)
        assert mock_session._session == dict(
            user_info=dict(
                user_id="spotify:user:user_id",
                access_token="access_token",
                access_token_expiry=expiry.isoformat(),
            ),
        )
        mock_db.upsert_user.assert_called_once_with("spotify:user:user_id", "refresh_token")
        mock_datetime_datetime.now.assert_called_once_with(datetime.timezone.utc)

    async def test_user_not_allowed(self, mock_session, mock_client_session_constructor):
        mock_config = unittest.mock.Mock()
        mock_config.get.side_effect = ["client_id", "client_secret",
                                       "http://callback_base_url", "spotify:user:test_user"]

        mock_db = unittest.mock.Mock()

        mock_login_failed_route = unittest.mock.Mock()
        mock_login_failed_route.url_for.return_value.with_query.return_value = "login_failed_route"

        mock_client_session = mock_client_session_constructor.return_value.__aenter__.return_value

        post_token_response = mock_client_session.post.return_value.__aenter__.return_value
        post_token_response.status = 200
        post_token_response.json.side_effect = (dict(
            access_token="access_token",
            expires_in=60,
            refresh_token="refresh_token",
        ),)

        get_profile_response = mock_client_session.get.return_value.__aenter__.return_value
        get_profile_response.status = 200
        get_profile_response.json.side_effect = (dict(
            uri="spotify:user:user_id",
        ),)

        resp = await smartlist.actions.login_callback(
            mock_config, mock_db, mock_session,
            "home_route", "artists_route", "login_callback_route",
            mock_login_failed_route, "state", None, "code")

        assert resp.status == 307
        assert resp.location == "login_failed_route"
        mock_config.get.assert_has_calls((
            unittest.mock.call("auth", "client_id"),
            unittest.mock.call("auth", "client_secret"),
            unittest.mock.call("auth", "callback_base_url"),
            unittest.mock.call("auth", "allowed_users", fallback=""),
        ))
        mock_client_session_constructor.assert_called_once_with()
        mock_client_session.post.assert_called_once_with(
            "https://accounts.spotify.com/api/token", data=dict(
                grant_type="authorization_code",
                client_id="client_id",
                client_secret="client_secret",
                code="code",
                redirect_uri="http://callback_base_url/login_callback_route",
            ))
        mock_client_session.get.assert_called_once_with(
            "https://api.spotify.com/v1/me", headers=dict(Authorization="Bearer access_token")
        )
        post_token_response.json.assert_called_once_with()
        get_profile_response.json.assert_called_once_with()

        assert mock_session._session == dict()
        mock_db.upsert_user.assert_not_called()
        mock_login_failed_route.assert_has_calls((
            unittest.mock.call.url_for(),
            unittest.mock.call.url_for().with_query(userId="spotify:user:user_id"),
        ))

    async def test_post_fail(self, mock_session, mock_client_session_constructor):
        mock_config = unittest.mock.Mock()
        mock_config.get.side_effect = ["client_id", "client_secret", "http://callback_base_url"]

        mock_client_session = mock_client_session_constructor.return_value.__aenter__.return_value

        post_token_response = mock_client_session.post.return_value.__aenter__.return_value
        post_token_response.status = 500

        resp = await smartlist.actions.login_callback(
            mock_config, None, mock_session,
            "home_route", "artists_route", "login_callback_route",
            None, "state", None, "code")

        assert resp.status == 307
        assert resp.location == "home_route"
        mock_config.get.assert_has_calls((
            unittest.mock.call("auth", "client_id"),
            unittest.mock.call("auth", "client_secret"),
            unittest.mock.call("auth", "callback_base_url"),
        ))
        mock_client_session_constructor.assert_called_once_with()
        mock_client_session.post.assert_called_once_with(
            "https://accounts.spotify.com/api/token", data=dict(
                grant_type="authorization_code",
                client_id="client_id",
                client_secret="client_secret",
                code="code",
                redirect_uri="http://callback_base_url/login_callback_route",
            ))
        mock_client_session.get.assert_not_called()
        post_token_response.json.assert_not_called()
        assert mock_session.pop_flashes() == [dict(
            type="error", msg="Encountered an error logging in.")]

    async def test_get_fails(self, mock_session, mock_client_session_constructor):
        mock_config = unittest.mock.Mock()
        mock_config.get.side_effect = ["client_id", "client_secret", "http://callback_base_url"]

        mock_client_session = mock_client_session_constructor.return_value.__aenter__.return_value

        post_token_response = mock_client_session.post.return_value.__aenter__.return_value
        post_token_response.status = 200
        post_token_response.json.side_effect = (dict(
            access_token="access_token",
            expires_in=60,
        ),)

        get_profile_response = mock_client_session.get.return_value.__aenter__.return_value
        get_profile_response.status = 500

        resp = await smartlist.actions.login_callback(
            mock_config, None, mock_session,
            "home_route", "artists_route", "login_callback_route",
            None, "state", None, "code")

        assert resp.status == 307
        assert resp.location == "home_route"
        mock_config.get.assert_has_calls((
            unittest.mock.call("auth", "client_id"),
            unittest.mock.call("auth", "client_secret"),
            unittest.mock.call("auth", "callback_base_url"),
        ))
        mock_client_session_constructor.assert_called_once_with()
        mock_client_session.post.assert_called_once_with(
            "https://accounts.spotify.com/api/token", data=dict(
                grant_type="authorization_code",
                client_id="client_id",
                client_secret="client_secret",
                code="code",
                redirect_uri="http://callback_base_url/login_callback_route",
            ))
        mock_client_session.get.assert_called_once_with(
            "https://api.spotify.com/v1/me", headers=dict(Authorization="Bearer access_token")
        )
        post_token_response.json.assert_called_once_with()
        get_profile_response.json.assert_not_called()
        assert mock_session.pop_flashes() == [dict(
            type="error", msg="Encountered an error logging in.")]


def test_logout():
    session = smartlist.session.Session({})
    session.user_info = "user_info"

    resp = smartlist.actions.logout(session, "home_route")

    assert resp.status == 307
    assert resp.location == "home_route"
    assert session.user_info is None
