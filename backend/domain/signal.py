"""Signal domain model — the standard record every scraper emits (spec §4)."""

import uuid
from dataclasses import dataclass, field


@dataclass
class Signal:
    person_name: str
    signal_type: str  # e.g. usaco_platinum, github_star_project, co_author
    signal_category: str  # competition | code | research | hackathon | connection | fellowship | debate
    signal_date: str  # ISO date the signal occurred/was observed
    signal_strength: float  # 0.0 - 1.0
    source: str  # scraper name, e.g. "github", "usaco"
    source_url: str = ""
    summary: str = ""  # human-readable one-liner, shown in evidence tables
    raw_data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    person_id: str | None = None  # set after entity resolution

    def __post_init__(self) -> None:
        if not 0.0 <= self.signal_strength <= 1.0:
            raise ValueError(f"signal_strength must be in [0,1], got {self.signal_strength}")
