"""SQLite connection provider + schema initialization."""

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA_PATH.read_text())
        self.conn.commit()

    def reset(self) -> None:
        """Drop everything and recreate. Used by build_db for idempotent rebuilds."""
        self.conn.execute("PRAGMA foreign_keys = OFF")
        cur = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for (table,) in cur.fetchall():
            self.conn.execute(f"DROP TABLE IF EXISTS {table}")
        self.conn.commit()
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.init_schema()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
