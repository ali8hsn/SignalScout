"""Portable persistence for human candidate launch reviews."""

from datetime import datetime, timezone

from backend.db.repositories.base import BaseRepository, chunked
from backend.domain.candidate_review import CandidateReview

REVIEW_STATES = {"pending", "approved", "rejected"}
SOURCE_BUCKETS = {"github_cross_source", "provider_discovered", "manual_public"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CandidateReviewRepository(BaseRepository):
    def get(self, person_id: str) -> CandidateReview | None:
        row = self.conn.execute(
            "SELECT * FROM candidate_reviews WHERE person_id = ?",
            (person_id,),
        ).fetchone()
        return self._to_model(row) if row else None

    def for_people(self, person_ids: list[str]) -> dict[str, CandidateReview]:
        """Batch variant of `get`: load every review for the given people in one
        query per chunk, keyed by `person_id` (people without a review are absent)."""
        reviews: dict[str, CandidateReview] = {}
        for chunk in chunked(person_ids, 400):
            placeholders = ",".join("?" for _ in chunk)
            rows = self.conn.execute(
                f"SELECT * FROM candidate_reviews WHERE person_id IN ({placeholders})",
                tuple(chunk),
            ).fetchall()
            for row in rows:
                model = self._to_model(row)
                reviews[model.person_id] = model
        return reviews

    def all(self, state: str | None = None) -> list[CandidateReview]:
        if state:
            rows = self.conn.execute(
                "SELECT * FROM candidate_reviews WHERE state = ? ORDER BY updated_at DESC",
                (state,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM candidate_reviews ORDER BY updated_at DESC"
            ).fetchall()
        return [self._to_model(row) for row in rows]

    def approved_contactable(self) -> list[CandidateReview]:
        rows = self.conn.execute(
            """SELECT * FROM candidate_reviews
               WHERE state = 'approved' AND contactable = 1
               ORDER BY approved_at ASC, person_id ASC"""
        ).fetchall()
        return [self._to_model(row) for row in rows]

    def upsert(
        self,
        person_id: str,
        state: str,
        why_now: str,
        notes: str,
        source_bucket: str,
        contactable: bool,
        primary_evidence_url: str,
        reviewer: str,
    ) -> CandidateReview:
        if state not in REVIEW_STATES:
            raise ValueError(f"Invalid review state: {state}")
        if source_bucket and source_bucket not in SOURCE_BUCKETS:
            raise ValueError(f"Invalid source bucket: {source_bucket}")
        existing = self.get(person_id)
        now = utc_now()
        approved_at = existing.approved_at if existing else None
        if state == "approved" and not approved_at:
            approved_at = now
        elif state != "approved":
            approved_at = None
        self.conn.execute(
            """INSERT INTO candidate_reviews
               (person_id, state, why_now, notes, source_bucket, contactable,
                primary_evidence_url, reviewer, approved_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(person_id) DO UPDATE SET
                 state = excluded.state,
                 why_now = excluded.why_now,
                 notes = excluded.notes,
                 source_bucket = excluded.source_bucket,
                 contactable = excluded.contactable,
                 primary_evidence_url = excluded.primary_evidence_url,
                 reviewer = excluded.reviewer,
                 approved_at = excluded.approved_at,
                 updated_at = excluded.updated_at""",
            (
                person_id,
                state,
                why_now.strip(),
                notes.strip(),
                source_bucket,
                int(contactable),
                primary_evidence_url.strip(),
                reviewer.strip(),
                approved_at,
                now,
            ),
        )
        self.conn.commit()
        return self.get(person_id)  # type: ignore[return-value]

    @staticmethod
    def _to_model(row) -> CandidateReview:
        return CandidateReview(
            person_id=row["person_id"],
            state=row["state"],
            why_now=row["why_now"],
            notes=row["notes"],
            source_bucket=row["source_bucket"],
            contactable=bool(row["contactable"]),
            primary_evidence_url=row["primary_evidence_url"],
            reviewer=row["reviewer"],
            approved_at=row["approved_at"],
            updated_at=row["updated_at"],
        )
