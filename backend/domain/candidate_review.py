"""Human launch-review record for a candidate."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateReview:
    person_id: str
    state: str = "pending"
    why_now: str = ""
    notes: str = ""
    source_bucket: str = ""
    contactable: bool = False
    primary_evidence_url: str = ""
    reviewer: str = ""
    approved_at: str | None = None
    updated_at: str = ""
