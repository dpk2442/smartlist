import configparser
import logging
import os
import sqlite3


logger = logging.getLogger(__name__)


class SmartListDB(object):

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def upsert_user(self, user_id, refresh_token):
        with self._conn as conn:
            conn.execute("""
                INSERT INTO users(user_id, refresh_token)
                VALUES(?, ?)
                ON CONFLICT(user_id) DO
                    UPDATE SET refresh_token = excluded.refresh_token
            """, (user_id, refresh_token))


def init_db(root_path: str, config: configparser.ConfigParser):
    schema_path = os.path.realpath(os.path.join(root_path, "schema.sql"))
    with open(schema_path, "r") as f:
        schema = f.read()

    db_path = os.path.realpath(os.path.join(root_path, config.get("db", "path")))
    logger.info("Connecting to db {}".format(db_path))

    conn = sqlite3.connect(db_path)
    with conn:
        conn.executescript(schema)

    return SmartListDB(conn)
