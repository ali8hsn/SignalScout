"""Typed connection edge between two people (plan: connections section)."""

import uuid
from dataclasses import dataclass, field

EDGE_TYPES = (
    "github_follows",
    "mutual_star",
    "co_author",
    "hackathon_teammate",
    "fellowship_cohort",
    "twitter_follows",
)

# Relative trust of an edge type when scoring connections.
EDGE_QUALITY: dict[str, float] = {
    "co_author": 1.0,
    "hackathon_teammate": 0.9,
    "fellowship_cohort": 0.8,
    "mutual_star": 0.6,
    "github_follows": 0.5,
    "twitter_follows": 0.4,
}


@dataclass
class GraphEdge:
    source_name: str  # person the edge points FROM (e.g. the follower / co-author)
    target_name: str  # person the edge points TO
    edge_type: str
    observed_date: str  # ISO date the edge was observed (backtest only counts pre-breakout edges)
    source: str  # data source, e.g. "github", "semantic_scholar", "seeded"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_person_id: str | None = None
    target_person_id: str | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.edge_type not in EDGE_TYPES:
            raise ValueError(f"unknown edge_type: {self.edge_type}")
