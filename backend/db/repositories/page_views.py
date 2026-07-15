"""Privacy-minimal page-view persistence."""

import uuid
from datetime import datetime, timezone

from backend.db.repositories.base import BaseRepository


class PageViewRepository(BaseRepository):
    def record(self, path: str, referrer: str | None = None) -> str:
        view_id = str(uuid.uuid4())
        viewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO page_views (id, path, viewed_at, referrer) VALUES (?, ?, ?, ?)",
            (view_id, path, viewed_at, referrer),
        )
        self.conn.commit()
        return view_id

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS count FROM page_views").fetchone()
        return int(row["count"])
