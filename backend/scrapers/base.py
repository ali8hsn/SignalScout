"""Abstract scraper contract: every source produces plain Signal records."""

from abc import ABC, abstractmethod

from backend.domain.signal import Signal


class BaseScraper(ABC):
    name: str = "base"

    @abstractmethod
    def scrape(self) -> list[Signal]:
        """Collect signals from the source. Must never raise on partial failure —
        degrade gracefully and return what was collected."""
