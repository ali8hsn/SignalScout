"""Shared repository helpers: JSON (de)serialization for TEXT columns."""

import json
import sqlite3

from backend.db.database import Database


class BaseRepository:
    def __init__(self, db: Database):
        self.db = db

    @property
    def conn(self) -> sqlite3.Connection:
        return self.db.conn

    @staticmethod
    def dumps(value) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def loads(text: str | None, default):
        if not text:
            return default
        return json.loads(text)
