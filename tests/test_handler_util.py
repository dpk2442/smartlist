import json
import unittest.mock

import aiohttp.web
import pytest

import smartlist.handler_util


@pytest.mark.asyncio
class TestRequireAuth(object):

    async def test_success(self):
        mock_handler = unittest.mock.AsyncMock()
        mock_session = unittest.mock.Mock()
        mock_session.user_info = "user_info"

        request = dict(session=mock_session)
        resp = await smartlist.handler_util.require_auth()(mock_handler)(request)

        assert resp == mock_handler.return_value
        mock_handler.assert_called_once_with(request)

    async def test_redirect(self):
        mock_handler = unittest.mock.AsyncMock()
        mock_session = unittest.mock.Mock()
        mock_session.user_info = None
        mock_request = unittest.mock.MagicMock()
        mock_request.__getitem__.return_value = mock_session
        mock_request.app.router.__getitem__.return_value.url_for.return_value = "url"

        with pytest.raises(aiohttp.web.HTTPFound) as exc:
            await smartlist.handler_util.require_auth()(mock_handler)(mock_request)

        assert exc.value.status == 302
        assert exc.value.location == "url"
        mock_request.__getitem__.assert_called_once_with("session")
        mock_request.app.router.__getitem__.assert_called_once_with("home")
        mock_handler.assert_not_called()

    async def test_no_redirect(self):
        mock_handler = unittest.mock.AsyncMock()
        mock_session = unittest.mock.Mock()
        mock_session.user_info = None
        mock_request = unittest.mock.MagicMock()
        mock_request.__getitem__.return_value = mock_session

        with pytest.raises(aiohttp.web.HTTPUnauthorized) as exc:
            await smartlist.handler_util.require_auth(
                redirect_on_fail=False)(mock_handler)(mock_request)

        assert exc.value.status == 401
        mock_handler.assert_not_called()
        mock_request.__getitem__.assert_called_once_with("session")


@pytest.mark.asyncio
class TestRequireCsrf(object):

    async def test_success(self):
        mock_handler = unittest.mock.AsyncMock()
        mock_session = unittest.mock.Mock()
        mock_session.csrf_token = "token"
        mock_request = unittest.mock.MagicMock()
        mock_request.__getitem__.return_value = mock_session
        mock_request.headers.getone.return_value = "token"

        resp = await smartlist.handler_util.require_csrf(mock_handler)(mock_request)

        assert resp == mock_handler.return_value
        mock_handler.assert_called_once_with(mock_request)
        mock_request.headers.getone.assert_called_once_with("X-CSRF-Token", default=None)
        mock_request.__getitem__.assert_called_once_with("session")

    async def test_mismatch(self):
        mock_handler = unittest.mock.AsyncMock()
        mock_session = unittest.mock.Mock()
        mock_session.csrf_token = "token1"
        mock_request = unittest.mock.MagicMock()
        mock_request.__getitem__.return_value = mock_session
        mock_request.headers.getone.return_value = "token2"

        with pytest.raises(aiohttp.web.HTTPUnauthorized) as exc:
            await smartlist.handler_util.require_csrf(mock_handler)(mock_request)

        assert exc.value.status == 401
        mock_handler.assert_not_called()
        mock_request.headers.getone.assert_called_once_with("X-CSRF-Token", default=None)
        mock_request.__getitem__.assert_called_once_with("session")


@pytest.mark.asyncio
class TestGetJsonPayload(object):

    async def test_success(self):
        mock_request = unittest.mock.AsyncMock()
        mock_request.json.return_value = "json"

        val = await smartlist.handler_util.get_json_payload(mock_request)

        assert val == "json"
        mock_request.json.assert_called_once_with()

    async def test_failure(self):
        mock_request = unittest.mock.AsyncMock()
        mock_request.json.side_effect = json.JSONDecodeError("msg", "doc", 0)

        with pytest.raises(aiohttp.web.HTTPBadRequest) as exc:
            await smartlist.handler_util.get_json_payload(mock_request)

        assert exc.value.status == 400
        mock_request.json.assert_called_once_with()
