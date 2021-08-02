import pytest
import unittest.mock

import smartlist.sync


@pytest.mark.asyncio
async def test_sync_artists(monkeypatch: pytest.MonkeyPatch):
    mock_sync_artist = unittest.mock.AsyncMock()
    monkeypatch.setattr("smartlist.sync.sync_artist", mock_sync_artist)

    mock_ws = unittest.mock.AsyncMock()
    mock_db = unittest.mock.Mock()
    mock_db.get_artists.return_value = ["a1", "a2", "a3"]

    await smartlist.sync.sync_artists(mock_ws, mock_db, "user_id", "client")

    mock_ws.send_json.assert_called_once_with(dict(type="start"))
    mock_db.get_artists.assert_called_once_with("user_id")
    mock_sync_artist.assert_has_calls((
        unittest.mock.call(mock_ws, mock_db, "user_id", "client", "a1"),
        unittest.mock.call(mock_ws, mock_db, "user_id", "client", "a2"),
        unittest.mock.call(mock_ws, mock_db, "user_id", "client", "a3"),
    ))
