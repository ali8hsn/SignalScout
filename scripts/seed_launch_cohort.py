"""Idempotently persist the publicly verified first launch cohort."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.container import Container
from backend.domain.person import Person
from backend.domain.signal import Signal

ROOT = Path(__file__).resolve().parent.parent
COHORT_FILE = ROOT / "data" / "launch_cohort.json"


def main() -> None:
    records = json.loads(COHORT_FILE.read_text())
    container = Container()
    for record in records:
        person = container.persons.get(record["person_id"])
        if person is None:
            person = Person(
                id=record["person_id"],
                name=record["name"],
                cohort="discovery",
                score=0,
                discovery_origin="manual_public",
                evidence_tier="verified",
            )
        person.name = record["name"]
        for field in (
            "github_username",
            "linkedin_url",
            "twitter_handle",
            "personal_site",
            "school",
            "current_location",
            "origin_location",
            "area",
        ):
            if record.get(field):
                setattr(person, field, record[field])
        container.persons.save(person)

        evidence_url = record["primary_evidence_url"]
        existing_urls = {
            signal.source_url for signal in container.signals.for_person(person.id)
        }
        if evidence_url not in existing_urls:
            if not record.get("signal_date"):
                raise ValueError(
                    f"{person.name}: primary evidence is not stored and has no signal details"
                )
            container.signals.save(
                Signal(
                    person_id=person.id,
                    person_name=person.name,
                    signal_type=record["signal_type"],
                    signal_category=record["signal_category"],
                    signal_date=record["signal_date"],
                    signal_strength=0.85,
                    source=record["signal_source"],
                    source_url=evidence_url,
                    summary=record["signal_summary"],
                    metadata={"reviewed_public_evidence": True},
                )
            )

        container.candidate_review_service.review(
            person_id=person.id,
            state="approved",
            why_now=record["why_now"],
            notes="Identity and claim checked against the persisted public evidence URL.",
            source_bucket=record["source_bucket"],
            contactable=True,
            primary_evidence_url=evidence_url,
            reviewer="launch-curation-public",
        )

    container.candidate_service.rescore_all()
    approved = container.candidate_review_service.list_rows("approved")
    print(f"approved {len(approved)} launch candidates")
    print(container.candidate_review_service.approved_mix())


if __name__ == "__main__":
    main()
