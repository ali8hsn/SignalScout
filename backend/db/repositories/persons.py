import sqlite3

from backend.db.repositories.base import BaseRepository
from backend.domain.person import Person


class PersonRepository(BaseRepository):
    def save(self, person: Person) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO persons
               (id, name, aliases, cohort, github_username, twitter_handle, linkedin_url, email,
                personal_site, contact_info, school, graduation_year, origin_location,
                current_location, region, fellowship, breakout_date, area, thesis, score,
                needs_review, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                person.id, person.name, self.dumps(person.aliases), person.cohort,
                person.github_username, person.twitter_handle, person.linkedin_url, person.email,
                person.personal_site, self.dumps(person.contact_info), person.school,
                person.graduation_year, person.origin_location, person.current_location,
                person.region, person.fellowship, person.breakout_date, person.area,
                person.thesis, person.score, int(person.needs_review), person.notes,
            ),
        )
        self.conn.commit()

    def save_many(self, persons: list[Person]) -> None:
        for p in persons:
            self.save(p)

    def get(self, person_id: str) -> Person | None:
        row = self.conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
        return self._to_model(row) if row else None

    def find_by_name(self, name: str) -> Person | None:
        row = self.conn.execute(
            "SELECT * FROM persons WHERE lower(name) = lower(?)", (name,)
        ).fetchone()
        return self._to_model(row) if row else None

    def find_by_github(self, username: str) -> Person | None:
        row = self.conn.execute(
            "SELECT * FROM persons WHERE lower(github_username) = lower(?)", (username,)
        ).fetchone()
        return self._to_model(row) if row else None

    def all(self, cohort: str | None = None) -> list[Person]:
        if cohort:
            rows = self.conn.execute("SELECT * FROM persons WHERE cohort = ?", (cohort,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM persons").fetchall()
        return [self._to_model(r) for r in rows]

    def update_score(self, person_id: str, score: float) -> None:
        self.conn.execute("UPDATE persons SET score = ? WHERE id = ?", (score, person_id))
        self.conn.commit()

    @staticmethod
    def _to_model(row: sqlite3.Row) -> Person:
        return Person(
            id=row["id"], name=row["name"],
            aliases=BaseRepository.loads(row["aliases"], []),
            cohort=row["cohort"], github_username=row["github_username"],
            twitter_handle=row["twitter_handle"], linkedin_url=row["linkedin_url"],
            email=row["email"], personal_site=row["personal_site"],
            contact_info=BaseRepository.loads(row["contact_info"], {}),
            school=row["school"], graduation_year=row["graduation_year"],
            origin_location=row["origin_location"], current_location=row["current_location"],
            region=row["region"], fellowship=row["fellowship"], breakout_date=row["breakout_date"],
            area=row["area"], thesis=row["thesis"], score=row["score"],
            needs_review=bool(row["needs_review"]), notes=row["notes"],
        )
