"""Validation and workflow rules for human launch approval."""

from urllib.parse import urlparse

from backend.db.repositories.candidate_reviews import CandidateReviewRepository
from backend.db.repositories.persons import PersonRepository
from backend.db.repositories.signals import SignalRepository
from backend.domain.candidate_review import CandidateReview


def _public_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class CandidateReviewService:
    def __init__(
        self,
        reviews: CandidateReviewRepository,
        persons: PersonRepository,
        signals: SignalRepository,
    ):
        self.reviews = reviews
        self.persons = persons
        self.signals = signals

    def review(
        self,
        person_id: str,
        state: str,
        why_now: str = "",
        notes: str = "",
        source_bucket: str = "",
        contactable: bool = False,
        primary_evidence_url: str = "",
        reviewer: str = "",
    ) -> CandidateReview:
        person = self.persons.get(person_id)
        if not person or person.cohort != "discovery":
            raise ValueError("Review target must be an existing discovery candidate.")
        if state == "approved":
            self._validate_approval(
                person_id,
                person.name,
                why_now,
                source_bucket,
                contactable,
                primary_evidence_url,
                bool(person.display_contacts()),
            )
        return self.reviews.upsert(
            person_id,
            state,
            why_now,
            notes,
            source_bucket,
            contactable,
            primary_evidence_url,
            reviewer,
        )

    def list_rows(self, state: str | None = None) -> list[dict]:
        results = []
        for review in self.reviews.all(state):
            person = self.persons.get(review.person_id)
            if not person:
                continue
            results.append(
                {
                    **review.__dict__,
                    "name": person.name,
                    "contacts": person.display_contacts(),
                }
            )
        return results

    def approved_mix(self) -> dict[str, int]:
        mix: dict[str, int] = {}
        for review in self.reviews.approved_contactable():
            mix[review.source_bucket] = mix.get(review.source_bucket, 0) + 1
        return dict(sorted(mix.items()))

    def _validate_approval(
        self,
        person_id: str,
        name: str,
        why_now: str,
        source_bucket: str,
        contactable: bool,
        primary_evidence_url: str,
        has_contact: bool,
    ) -> None:
        if not name.strip() or name.strip().lower() in {"unknown", "anonymous"}:
            raise ValueError("Approval requires an anchored real name.")
        if len(why_now.strip()) < 30:
            raise ValueError("Approval requires a specific reviewed why-now (30+ characters).")
        if not _public_http_url(primary_evidence_url):
            raise ValueError("Approval requires a valid public primary evidence URL.")
        if not source_bucket:
            raise ValueError("Approval requires an honest source bucket.")
        if not contactable or not has_contact:
            raise ValueError("Approval requires at least one profile or contact route.")
        evidence_urls = {
            signal.source_url
            for signal in self.signals.for_person(person_id)
            if _public_http_url(signal.source_url)
        }
        if primary_evidence_url not in evidence_urls:
            raise ValueError(
                "Primary evidence URL must be persisted on a candidate signal before approval."
            )
