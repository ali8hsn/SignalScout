"""Loads curated signal fixtures from data/seed_signals/*.json.

Every non-GitHub source is seeded for the demo (locked decision in plan.md);
fixture shape mirrors exactly what a live scraper for that source would emit,
so swapping in a real scraper later only changes the transport.
"""

import json
from pathlib import Path

from backend.domain.signal import Signal
from backend.scrapers.base import BaseScraper


class SeededScraper(BaseScraper):
    def __init__(self, fixture_path: Path):
        self.fixture_path = fixture_path
        self.name = fixture_path.stem

    def scrape(self) -> list[Signal]:
        if not self.fixture_path.exists():
            return []
        data = json.loads(self.fixture_path.read_text())
        source = data.get("source", self.name)
        category = data.get("category", "other")
        signals = []
        for row in data.get("signals", []):
            signals.append(
                Signal(
                    person_name=row["person_name"],
                    signal_type=row["signal_type"],
                    signal_category=row.get("signal_category", category),
                    signal_date=row["signal_date"],
                    signal_strength=row["signal_strength"],
                    source=source,
                    source_url=row.get("source_url", ""),
                    summary=row.get("summary", ""),
                    raw_data=row.get("raw_data", {}),
                    metadata=row.get("metadata", {}),
                )
            )
        return signals
