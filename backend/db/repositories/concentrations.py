import sqlite3

from backend.db.repositories.base import BaseRepository
from backend.domain.concentration import Concentration


class ConcentrationRepository(BaseRepository):
    def replace_all(self, concentrations: list[Concentration]) -> None:
        self.conn.execute("DELETE FROM concentrations")
        for c in concentrations:
            self.conn.execute(
                """INSERT INTO concentrations (id, kind, key, count, person_ids, person_names, computed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (c.id, c.kind, c.key, c.count, self.dumps(c.person_ids),
                 self.dumps(c.person_names), c.computed_at),
            )
        self.conn.commit()

    def all(self) -> list[Concentration]:
        rows = self.conn.execute(
            "SELECT * FROM concentrations ORDER BY count DESC"
        ).fetchall()
        return [self._to_model(r) for r in rows]

    @staticmethod
    def _to_model(row: sqlite3.Row) -> Concentration:
        return Concentration(
            id=row["id"], kind=row["kind"], key=row["key"], count=row["count"],
            person_ids=BaseRepository.loads(row["person_ids"], []),
            person_names=BaseRepository.loads(row["person_names"], []),
            computed_at=row["computed_at"],
        )
