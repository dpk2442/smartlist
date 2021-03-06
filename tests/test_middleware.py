import unittest.mock

import pytest

import smartlist.middleware


@pytest.fixture
def mock_session(monkeypatch: pytest.MonkeyPatch):
    mock_get_session = unittest.mock.AsyncMock()
    monkeypatch.setattr("smartlist.middleware.smartlist.session.get_session", mock_get_session)
    return mock_get_session.return_value


@pytest.mark.asyncio
async def test_load_session(monkeypatch: pytest.MonkeyPatch):
    mock_get_session = unittest.mock.AsyncMock()
    mock_get_session.return_value = "session"
    monkeypatch.setattr("smartlist.middleware.smartlist.session.get_session", mock_get_session)

    mock_request = {}
    mock_handler = unittest.mock.AsyncMock()
    await smartlist.middleware.load_session(mock_request, mock_handler)

    assert mock_request == {
        "session": "session",
    }
    mock_get_session.assert_called_once_with(mock_request)
    mock_handler.assert_called_once_with(mock_request)


@pytest.mark.asyncio
async def test_inject_client(monkeypatch: pytest.MonkeyPatch,
                             mock_session: unittest.mock.AsyncMock):
    mock_spotify_client_constructor = unittest.mock.Mock()
    mock_spotify_client_constructor.return_value.close = unittest.mock.AsyncMock()
    monkeypatch.setattr("smartlist.middleware.smartlist.client.SpotifyClient",
                        mock_spotify_client_constructor)

    mock_request = unittest.mock.MagicMock()
    mock_request.app.__getitem__.side_effect = ["config", "db"]

    mock_handler = unittest.mock.AsyncMock()
    await smartlist.middleware.inject_client(mock_request, mock_handler)

    mock_request.app.__getitem__.assert_has_calls((
        unittest.mock.call("config"),
        unittest.mock.call("db"),
    ))
    mock_request.__setitem__.assert_called_once_with(
        "client", mock_spotify_client_constructor.return_value)
    mock_spotify_client_constructor.assert_called_once_with("config", "db", mock_session)
    mock_handler.assert_called_once_with(mock_request)
    mock_spotify_client_constructor.return_value.close.assert_called_once_with()


@pytest.mark.asyncio
class TestGenerateCsrfToken(object):

    @pytest.fixture
    def mock_token_urlsafe(self, monkeypatch: pytest.MonkeyPatch):
        mock = unittest.mock.Mock()
        monkeypatch.setattr("smartlist.middleware.secrets.token_urlsafe", mock)
        return mock

    async def test_no_existing_token(self,
                                     mock_session: unittest.mock.AsyncMock,
                                     mock_token_urlsafe: unittest.mock.Mock):
        mock_session.csrf_token = None
        mock_token_urlsafe.return_value = "token"

        mock_handler = unittest.mock.AsyncMock()
        await smartlist.middleware.generate_csrf_token("request", mock_handler)

        assert mock_session.csrf_token == "token"
        mock_token_urlsafe.assert_called_once_with()
        mock_handler.assert_called_once_with("request")

    async def test_existing_token(self,
                                  mock_session: unittest.mock.AsyncMock,
                                  mock_token_urlsafe: unittest.mock.Mock):
        mock_session.csrf_token = "token"
        mock_token_urlsafe.return_value = "new_token"

        mock_handler = unittest.mock.AsyncMock()
        await smartlist.middleware.generate_csrf_token("request", mock_handler)

        assert mock_session.csrf_token == "token"
        mock_token_urlsafe.assert_not_called()
        mock_handler.assert_called_once_with("request")
