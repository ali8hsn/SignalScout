"""ConcentrationDetector (spec §9): schools/regions producing 3+ flagged candidates."""

from collections import defaultdict
from datetime import date

from backend.db.repositories.concentrations import ConcentrationRepository
from backend.domain.concentration import Concentration
from backend.domain.person import Person

MIN_CLUSTER = 3


class ConcentrationDetector:
    def __init__(self, repo: ConcentrationRepository):
        self.repo = repo

    def compute(self, flagged: list[Person]) -> list[Concentration]:
        buckets: dict[tuple[str, str], list[Person]] = defaultdict(list)
        for person in flagged:
            if person.school:
                buckets[("school", person.school.split("(")[0].strip())].append(person)
            if person.region:
                buckets[("region", person.region)].append(person)
            if person.fellowship:
                program = person.fellowship.rsplit(" ", 1)[0]  # "Thiel Fellowship 2014" -> program
                buckets[("program", program)].append(person)

        today = date.today().isoformat()
        concentrations = [
            Concentration(
                kind=kind, key=key, count=len(members),
                person_ids=[m.id for m in members], person_names=[m.name for m in members],
                computed_at=today,
            )
            for (kind, key), members in buckets.items()
            if len(members) >= MIN_CLUSTER
        ]
        concentrations.sort(key=lambda c: -c.count)
        self.repo.replace_all(concentrations)
        return concentrations
