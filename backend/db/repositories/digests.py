import sqlite3
from dataclasses import asdict

from backend.db.repositories.base import BaseRepository
from backend.domain.digest import Digest, DigestEntry


class DigestRepository(BaseRepository):
    def save(self, digest: Digest) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO digests (id, generated_at, subject, entries, html)
               VALUES (?, ?, ?, ?, ?)""",
            (digest.id, digest.generated_at, digest.subject,
             self.dumps([asdict(e) for e in digest.entries]), digest.html),
        )
        self.conn.commit()

    def latest(self) -> Digest | None:
        row = self.conn.execute(
            "SELECT * FROM digests ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()
        return self._to_model(row) if row else None

    @staticmethod
    def _to_model(row: sqlite3.Row) -> Digest:
        entries = [DigestEntry(**e) for e in BaseRepository.loads(row["entries"], [])]
        return Digest(
            id=row["id"], generated_at=row["generated_at"], subject=row["subject"],
            entries=entries, html=row["html"],
        )
