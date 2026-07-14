import sqlite3

from backend.db.repositories.base import BaseRepository
from backend.domain.signal import Signal


class SignalRepository(BaseRepository):
    def save(self, signal: Signal) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO signals
               (id, person_id, person_name, signal_type, signal_category, signal_date,
                signal_strength, source, source_url, summary, raw_data, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal.id, signal.person_id, signal.person_name, signal.signal_type,
                signal.signal_category, signal.signal_date, signal.signal_strength,
                signal.source, signal.source_url, signal.summary,
                self.dumps(signal.raw_data), self.dumps(signal.metadata),
            ),
        )

    def save_many(self, signals: list[Signal]) -> None:
        for s in signals:
            self.save(s)
        self.conn.commit()

    def for_person(self, person_id: str, before: str | None = None) -> list[Signal]:
        if before:
            rows = self.conn.execute(
                "SELECT * FROM signals WHERE person_id = ? AND signal_date < ? ORDER BY signal_date",
                (person_id, before),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM signals WHERE person_id = ? ORDER BY signal_date", (person_id,)
            ).fetchall()
        return [self._to_model(r) for r in rows]

    def unresolved(self) -> list[Signal]:
        rows = self.conn.execute("SELECT * FROM signals WHERE person_id IS NULL").fetchall()
        return [self._to_model(r) for r in rows]

    def assign_person(self, signal_id: str, person_id: str) -> None:
        self.conn.execute("UPDATE signals SET person_id = ? WHERE id = ?", (person_id, signal_id))

    def commit(self) -> None:
        self.conn.commit()

    @staticmethod
    def _to_model(row: sqlite3.Row) -> Signal:
        return Signal(
            id=row["id"], person_id=row["person_id"], person_name=row["person_name"],
            signal_type=row["signal_type"], signal_category=row["signal_category"],
            signal_date=row["signal_date"], signal_strength=row["signal_strength"],
            source=row["source"], source_url=row["source_url"], summary=row["summary"],
            raw_data=BaseRepository.loads(row["raw_data"], {}),
            metadata=BaseRepository.loads(row["metadata"], {}),
        )
