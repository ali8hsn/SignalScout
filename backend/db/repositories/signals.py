import sqlite3

from backend.db.repositories.base import BaseRepository, chunked
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
            # Inclusive of the boundary date: a signal dated exactly on a founder's
            # breakout day (e.g. fellowship-cohort seed signals) counts as known
            # "as of breakout", so the backtest doesn't drop same-day evidence.
            rows = self.conn.execute(
                "SELECT * FROM signals WHERE person_id = ? AND signal_date <= ? ORDER BY signal_date",
                (person_id, before),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM signals WHERE person_id = ? ORDER BY signal_date", (person_id,)
            ).fetchall()
        return [self._to_model(r) for r in rows]

    def for_people(self, person_ids: list[str]) -> dict[str, list[Signal]]:
        """Batch variant of `for_person`: one query per chunk instead of one per
        person, returning signals grouped by `person_id` (ascending signal_date)."""
        grouped: dict[str, list[Signal]] = {pid: [] for pid in person_ids}
        for chunk in chunked(person_ids, 400):
            placeholders = ",".join("?" for _ in chunk)
            rows = self.conn.execute(
                f"SELECT * FROM signals WHERE person_id IN ({placeholders}) ORDER BY signal_date",
                tuple(chunk),
            ).fetchall()
            for row in rows:
                model = self._to_model(row)
                grouped.setdefault(model.person_id, []).append(model)
        return grouped

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
