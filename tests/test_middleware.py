import unittest.mock

import pytest

import smartlist.middleware


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
