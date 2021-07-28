import configparser
import logging
import os
import sqlite3


logger = logging.getLogger(__name__)


EXPECTED_DB_VERSION = 1
DB_SCHEMA_SCRIPTS = {
    1: """
        CREATE TABLE users(
            user_id UNIQUE,
            refresh_token
        );
    """,
}


def apply_db_scripts(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("PRAGMA user_version")
    current_version = cur.fetchone()[0]

    if current_version == EXPECTED_DB_VERSION:
        return

    if current_version > EXPECTED_DB_VERSION:
        raise Exception("Unknown version {} for database".format(current_version))

    logger.info("DB is for version {}, current expected version is {}".format(
        current_version, EXPECTED_DB_VERSION))
    for idx in range(current_version + 1, EXPECTED_DB_VERSION + 1):
        logger.info("Running script for version {}".format(idx))
        cur.executescript(DB_SCHEMA_SCRIPTS[idx])

    cur.execute("PRAGMA user_version = {}".format(EXPECTED_DB_VERSION))


def init_db(root_path: str, config: configparser.ConfigParser):
    db_path = os.path.realpath(os.path.join(root_path, config.get("db", "path")))
    logger.info("Connecting to db {}".format(db_path))

    conn = sqlite3.connect(db_path)
    apply_db_scripts(conn)

    return SmartListDB(conn)


class SmartListDB(object):

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def get_refresh_token(self, user_id):
        with self._conn as conn:
            cur = conn.execute("SELECT refresh_token FROM users WHERE user_id = ?", (user_id,))
            return cur.fetchone()[0]

    def upsert_user(self, user_id, refresh_token):
        with self._conn as conn:
            conn.execute("""
                INSERT INTO users(user_id, refresh_token)
                VALUES(?, ?)
                ON CONFLICT(user_id) DO
                    UPDATE SET refresh_token = excluded.refresh_token
            """, (user_id, refresh_token))
