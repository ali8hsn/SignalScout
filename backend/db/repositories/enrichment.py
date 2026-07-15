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
    provider TEXT NOT NULL,
    lane TEXT NOT NULL DEFAULT 'enrich',  -- 'search' | 'enrich'
    day TEXT NOT NULL,                     -- YYYY-MM-DD (UTC)
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (provider, lane, day)
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
    """Provider-scoped daily usage; monthly budgets aggregate over the day rows.

    Rows are keyed (provider, lane, day) so PDL's search vs. GitHub-enrichment
    lanes and Coresignal's separate daily cap are all tracked independently.
    """

    def __init__(self, db: Database):
        super().__init__(db)
        self._migrate_legacy_schema()
        self.conn.executescript(USAGE_TABLE_SQL)
        self.conn.commit()

    def _migrate_legacy_schema(self) -> None:
        """The original enrichment_usage was a global day->count counter with no
        provider/lane columns. It is empty in the live DB, so migrating means
        dropping the legacy shape before the provider-scoped table is created.
        Works for both SQLite and Postgres (PostgresConnection no-ops PRAGMA)."""
        if not self._has_legacy_usage_table():
            return
        self.conn.execute("DROP TABLE IF EXISTS enrichment_usage")
        self.conn.commit()

    def _has_legacy_usage_table(self) -> bool:
        if self.db.backend == "postgres":
            row = self.conn.execute(
                """SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'enrichment_usage'
                     AND column_name = 'day'""",
            ).fetchone()
            has_day = row is not None
            row = self.conn.execute(
                """SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'enrichment_usage'
                     AND column_name = 'provider'""",
            ).fetchone()
            has_provider = row is not None
            return has_day and not has_provider
        cols = self.conn.execute("PRAGMA table_info(enrichment_usage)").fetchall()
        names = {row["name"] for row in cols}
        return "day" in names and "provider" not in names

    def count_for(self, provider: str, day: str, lane: str | None = None) -> int:
        """Fresh lookups recorded for a provider on a UTC day (optionally one lane)."""
        if lane is None:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(count), 0) AS total FROM enrichment_usage "
                "WHERE provider = ? AND day = ?",
                (provider, day),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(count), 0) AS total FROM enrichment_usage "
                "WHERE provider = ? AND day = ? AND lane = ?",
                (provider, day, lane),
            ).fetchone()
        return row["total"] if row else 0

    def count_for_month(self, provider: str, month: str, lane: str | None = None) -> int:
        """Fresh lookups recorded for a provider across a YYYY-MM month."""
        prefix = f"{month}-%"
        if lane is None:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(count), 0) AS total FROM enrichment_usage "
                "WHERE provider = ? AND day LIKE ?",
                (provider, prefix),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(count), 0) AS total FROM enrichment_usage "
                "WHERE provider = ? AND day LIKE ? AND lane = ?",
                (provider, prefix, lane),
            ).fetchone()
        return row["total"] if row else 0

    def increment(self, provider: str, lane: str, day: str, by: int = 1) -> None:
        self.conn.execute(
            """INSERT INTO enrichment_usage (provider, lane, day, count)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(provider, lane, day) DO UPDATE SET count = count + excluded.count""",
            (provider, lane, day, by),
        )
        self.conn.commit()
