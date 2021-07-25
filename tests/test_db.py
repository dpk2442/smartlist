import unittest.mock

import pytest

import smartlist.db


def test_constructor():
    db = smartlist.db.SmartListDB("conn")
    assert db._conn == "conn"


def test_get_refresh_token():
    mock_conn = unittest.mock.MagicMock()
    mock_conn.__enter__.return_value.execute.return_value.fetchone.return_value = ["refresh_token"]

    db = smartlist.db.SmartListDB(mock_conn)
    result = db.get_refresh_token("user_id")

    assert result == "refresh_token"
    mock_conn.__enter__.return_value.execute.assert_called_once_with(
        unittest.mock.ANY,
        ("user_id",),
    )
    mock_conn.__enter__.return_value.execute.return_value.fetchone.assert_called_once_with()


def test_upsert_user():
    mock_conn = unittest.mock.MagicMock()
    db = smartlist.db.SmartListDB(mock_conn)
    db.upsert_user("user_id", "refresh_token")

    mock_conn.__enter__.return_value.execute.assert_called_once_with(
        unittest.mock.ANY,
        ("user_id", "refresh_token"),
    )


def test_init_db(monkeypatch: pytest.MonkeyPatch):
    mock_open = unittest.mock.mock_open(read_data="schema")

    mock_connect = unittest.mock.MagicMock()
    monkeypatch.setattr("smartlist.db.sqlite3.connect", mock_connect)

    mock_config = unittest.mock.Mock()
    mock_config.get.return_value = "db_path"

    with unittest.mock.patch("builtins.open", mock_open):
        db = smartlist.db.init_db("/root_path", mock_config)

    assert db is not None
    assert isinstance(db, smartlist.db.SmartListDB)
    assert db._conn == mock_connect.return_value
    mock_open.assert_called_once_with("/root_path/schema.sql", "r")
    mock_connect.assert_called_once_with("/root_path/db_path")
    mock_connect.return_value.executescript.assert_called_once_with("schema")
