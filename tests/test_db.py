import unittest.mock

import pytest

import smartlist.db


def test_scripts_exist():
    for idx in range(1, smartlist.db.EXPECTED_DB_VERSION + 1):
        assert idx in smartlist.db.DB_SCHEMA_SCRIPTS


class TestApplyDbScripts(object):

    def test_expected_version(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("smartlist.db.EXPECTED_DB_VERSION", 5)

        mock_conn = unittest.mock.Mock()
        mock_cur = mock_conn.cursor.return_value
        mock_cur.fetchone.return_value = (5,)

        smartlist.db.apply_db_scripts(mock_conn)

        mock_cur.execute.assert_called_once_with("PRAGMA user_version")
        mock_cur.fetchone.assert_called_once_with()

    def test_unknown_version(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("smartlist.db.EXPECTED_DB_VERSION", 5)

        mock_conn = unittest.mock.Mock()
        mock_cur = mock_conn.cursor.return_value
        mock_cur.fetchone.return_value = (7,)

        with pytest.raises(Exception, match="Unknown version 7 for database"):
            smartlist.db.apply_db_scripts(mock_conn)

        mock_cur.execute.assert_called_once_with("PRAGMA user_version")
        mock_cur.fetchone.assert_called_once_with()

    def test_upgrades_needed(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("smartlist.db.EXPECTED_DB_VERSION", 5)
        monkeypatch.setattr("smartlist.db.DB_SCHEMA_SCRIPTS", {
            3: "script3",
            4: "script4",
            5: "script5",
        })

        mock_conn = unittest.mock.Mock()
        mock_cur = mock_conn.cursor.return_value
        mock_cur.fetchone.return_value = (2,)

        smartlist.db.apply_db_scripts(mock_conn)

        mock_cur.assert_has_calls((
            unittest.mock.call.execute("PRAGMA user_version"),
            unittest.mock.call.fetchone(),
            unittest.mock.call.executescript("script3"),
            unittest.mock.call.executescript("script4"),
            unittest.mock.call.executescript("script5"),
            unittest.mock.call.execute("PRAGMA user_version = 5"),
        ))


def test_init_db(monkeypatch: pytest.MonkeyPatch):
    mock_apply_db_scripts = unittest.mock.Mock()
    monkeypatch.setattr("smartlist.db.apply_db_scripts", mock_apply_db_scripts)

    mock_connect = unittest.mock.MagicMock()
    monkeypatch.setattr("smartlist.db.sqlite3.connect", mock_connect)

    mock_config = unittest.mock.Mock()
    mock_config.get.return_value = "db_path"

    db = smartlist.db.init_db("/root_path", mock_config)

    assert db is not None
    assert isinstance(db, smartlist.db.SmartListDB)
    assert db._conn == mock_connect.return_value
    mock_connect.assert_called_once_with("/root_path/db_path")
    mock_apply_db_scripts.assert_called_once_with(mock_connect.return_value)


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


def test_get_artists():
    mock_conn = unittest.mock.MagicMock()
    mock_conn.__enter__.return_value.execute.return_value.fetchall.return_value = (
        ("id1",),
        ("id2",),
    )

    db = smartlist.db.SmartListDB(mock_conn)
    artists = db.get_artists("user_id")

    assert artists == [dict(id="id1"), dict(id="id2")]
    mock_conn.__enter__.return_value.execute.assert_called_once_with(
        unittest.mock.ANY,
        ("user_id",),
    )
    mock_conn.__enter__.return_value.execute.return_value.fetchall.assert_called_once_with()


def test_add_artists():
    mock_conn = unittest.mock.MagicMock()
    db = smartlist.db.SmartListDB(mock_conn)
    db.add_artists("user_id", ("a1", "a2", "a3"))

    mock_conn.__enter__.return_value.executemany.assert_called_once_with(
        unittest.mock.ANY,
        [
            ("user_id", "a1"),
            ("user_id", "a2"),
            ("user_id", "a3"),
        ],
    )


def test_remove_artists():
    mock_conn = unittest.mock.MagicMock()
    db = smartlist.db.SmartListDB(mock_conn)
    db.remove_artists("user_id", ("a1", "a2", "a3"))

    mock_conn.__enter__.return_value.executemany.assert_called_once_with(
        unittest.mock.ANY,
        [
            ("user_id", "a1"),
            ("user_id", "a2"),
            ("user_id", "a3"),
        ],
    )
