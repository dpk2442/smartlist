import pytest
import unittest.mock

import aiohttp.web

import smartlist.actions


def test_login():
    config = unittest.mock.Mock()
    config.get.side_effect = ["client_id", "http://base_url"]

    resp = smartlist.actions.login(config, "login_callback")

    assert resp.status == 307
    assert resp.location == (
        "https://accounts.spotify.com/authorize?client_id=client_id&response_type=code&" +
        "redirect_uri=http%3A%2F%2Fbase_url%2Flogin_callback&state=test&scope="
    )
    config.get.assert_has_calls((
        unittest.mock.call("auth", "client_id"),
        unittest.mock.call("auth", "callback_base_url"),
    ))


@pytest.mark.asyncio
class TestLoginCallback(object):

    @pytest.fixture
    def mock_client_session_constructor(self, monkeypatch):
        mock = unittest.mock.MagicMock()
        mock.return_value.__aenter__.return_value.post = unittest.mock.MagicMock()
        mock.return_value.__aenter__.return_value.get = unittest.mock.MagicMock()
        monkeypatch.setattr("aiohttp.ClientSession", mock)
        return mock

    async def test_bad_state(self):
        resp = await smartlist.actions.login_callback(None, "home_route", None, None, None, None)
        assert resp.status == 307
        assert resp.location == "home_route"

    async def test_error(self):
        resp = await smartlist.actions.login_callback(
            None, "home_route", None, "test", "error", None)
        assert resp.status == 307
        assert resp.location == "home_route"

    async def test_missing_code(self):
        resp = await smartlist.actions.login_callback(None, "home_route", None, "test", None, None)
        assert resp.status == 307
        assert resp.location == "home_route"

    async def test_success(self, mock_client_session_constructor):
        mock_config = unittest.mock.Mock()
        mock_config.get.side_effect = ["client_id", "client_secret", "http://callback_base_url"]

        mock_client_session = mock_client_session_constructor.return_value.__aenter__.return_value

        post_token_response = mock_client_session.post.return_value.__aenter__.return_value
        post_token_response.status = 200
        post_token_response.json.side_effect = (dict(
            access_token="access_token"
        ),)

        get_profile_response = mock_client_session.get.return_value.__aenter__.return_value
        get_profile_response.status = 200
        get_profile_response.json.side_effect = ("get_profile_response",)

        resp = await smartlist.actions.login_callback(
            mock_config, "home_route", "login_callback_route", "test", None, "code")

        assert resp.status == 200
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
        get_profile_response.json.assert_called_once_with()

    async def test_post_fail(self, mock_client_session_constructor):
        mock_config = unittest.mock.Mock()
        mock_config.get.side_effect = ["client_id", "client_secret", "http://callback_base_url"]

        mock_client_session = mock_client_session_constructor.return_value.__aenter__.return_value

        post_token_response = mock_client_session.post.return_value.__aenter__.return_value
        post_token_response.status = 500

        resp = await smartlist.actions.login_callback(
            mock_config, "home_route", "login_callback_route", "test", None, "code")

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

    async def test_get_fails(self, mock_client_session_constructor):
        mock_config = unittest.mock.Mock()
        mock_config.get.side_effect = ["client_id", "client_secret", "http://callback_base_url"]

        mock_client_session = mock_client_session_constructor.return_value.__aenter__.return_value

        post_token_response = mock_client_session.post.return_value.__aenter__.return_value
        post_token_response.status = 200
        post_token_response.json.side_effect = (dict(
            access_token="access_token"
        ),)

        get_profile_response = mock_client_session.get.return_value.__aenter__.return_value
        get_profile_response.status = 500

        resp = await smartlist.actions.login_callback(
            mock_config, "home_route", "login_callback_route", "test", None, "code")

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
