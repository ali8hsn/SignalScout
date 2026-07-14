"""A hotspot of flagged candidates: school, program, or geographic region (spec §9)."""

import uuid
from dataclasses import dataclass, field


@dataclass
class Concentration:
    kind: str  # school | region | program
    key: str  # e.g. "MIT", "Research Triangle", "Z Fellows"
    count: int
    person_ids: list[str]
    person_names: list[str]
    computed_at: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
