"""Shared repository helpers: JSON (de)serialization for TEXT columns."""

import json
import sqlite3
from collections.abc import Iterator, Sequence
from typing import TypeVar

from backend.db.database import Database

T = TypeVar("T")


def chunked(items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    """Yield successive `size`-length slices — used to keep `IN (...)` parameter
    counts under SQLite's per-statement variable limit on batch loads."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


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
