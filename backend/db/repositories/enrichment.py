"""Repositories for the licensed-enrichment guardrail tables.

Both self-create their tables (CREATE IF NOT EXISTS) because the live
signal_scout.db predates them and is never reset/rebuilt.
"""

from backend.db.database import Database
from backend.db.repositories.base import BaseRepository

CACHE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS enrichment_cache (
    cache_key TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    person_id TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_enrichment_cache_person ON enrichment_cache(person_id);
"""

USAGE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS enrichment_usage (
    day TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0
);
"""


class EnrichmentCacheRepository(BaseRepository):
    def __init__(self, db: Database):
        super().__init__(db)
        self.conn.executescript(CACHE_TABLE_SQL)
        self.conn.commit()

    def get(self, provider: str, person_id: str) -> tuple[dict, str] | None:
        """(payload, fetched_at ISO) for this provider+person, or None if never fetched.
        An empty payload dict means a cached miss — still authoritative inside the TTL."""
        row = self.conn.execute(
            "SELECT payload, fetched_at FROM enrichment_cache WHERE cache_key = ?",
            (self._key(provider, person_id),),
        ).fetchone()
        if row is None:
            return None
        return self.loads(row["payload"], {}), row["fetched_at"]

    def put(self, provider: str, person_id: str, payload: dict, fetched_at: str) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO enrichment_cache
               (cache_key, provider, person_id, payload, fetched_at)
               VALUES (?, ?, ?, ?, ?)""",
            (self._key(provider, person_id), provider, person_id, self.dumps(payload), fetched_at),
        )
        self.conn.commit()

    @staticmethod
    def _key(provider: str, person_id: str) -> str:
        return f"{provider}:{person_id}"


class EnrichmentUsageRepository(BaseRepository):
    def __init__(self, db: Database):
        super().__init__(db)
        self.conn.executescript(USAGE_TABLE_SQL)
        self.conn.commit()

    def count_for(self, day: str) -> int:
        row = self.conn.execute(
            "SELECT count FROM enrichment_usage WHERE day = ?", (day,)
        ).fetchone()
        return row["count"] if row else 0

    def increment(self, day: str, by: int = 1) -> None:
        self.conn.execute(
            """INSERT INTO enrichment_usage (day, count) VALUES (?, ?)
               ON CONFLICT(day) DO UPDATE SET count = count + excluded.count""",
            (day, by),
        )
        self.conn.commit()
