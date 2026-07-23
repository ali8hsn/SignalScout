"""Privacy-minimal page-view persistence."""

import uuid
from datetime import datetime, timezone

from backend.db.repositories.base import BaseRepository

# Hard cap on retained rows. page_views is append-only from an open public
# endpoint, so without a cap it grows unbounded; we keep only the most recent
# MAX_ROWS and prune the overflow occasionally (every PRUNE_INTERVAL inserts).
MAX_ROWS = 50_000
PRUNE_INTERVAL = 500


class PageViewRepository(BaseRepository):
    def __init__(self, db):
        super().__init__(db)
        self._inserts_since_prune = 0

    def record(self, path: str, referrer: str | None = None) -> str:
        view_id = str(uuid.uuid4())
        viewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO page_views (id, path, viewed_at, referrer) VALUES (?, ?, ?, ?)",
            (view_id, path, viewed_at, referrer),
        )
        self.conn.commit()
        self._inserts_since_prune += 1
        if self._inserts_since_prune >= PRUNE_INTERVAL:
            self._inserts_since_prune = 0
            self.prune()
        return view_id

    def prune(self, max_rows: int = MAX_ROWS) -> int:
        """Delete all but the most recent `max_rows` rows. Returns rows removed."""
        cursor = self.conn.execute(
            """DELETE FROM page_views
               WHERE id NOT IN (
                   SELECT id FROM page_views
                   ORDER BY viewed_at DESC, id DESC
                   LIMIT ?
               )""",
            (max_rows,),
        )
        self.conn.commit()
        return cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS count FROM page_views").fetchone()
        return int(row["count"])
