"""Background ticker that periodically delivers due subscriber digests.

Mirrors DiscoveryScheduler: a fresh Container per tick keeps SQLite/Postgres
connections thread-local, and each tick calls SubscriberDigestService.run_due,
which is idempotent per cadence window (a subscriber is never emailed twice
inside their interval). Disabled with DIGEST_BACKGROUND=0.
"""

import logging
import threading
import time
from collections.abc import Callable

from backend.config import Settings

logger = logging.getLogger(__name__)


class DigestScheduler:
    def __init__(
        self,
        settings: Settings,
        container_factory: Callable[[], object],
    ):
        self.settings = settings
        self.container_factory = container_factory
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.settings.digest_background:
            logger.info("Digest background scheduler disabled")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="digest-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Digest background scheduler started (interval=%sh)",
            self.settings.digest_background_interval_hours,
        )

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)
        self._thread = None

    def _loop(self) -> None:
        # Short initial delay so the HTTP server finishes binding first.
        if self._stop.wait(20):
            return
        while not self._stop.is_set():
            self._tick()
            hours = max(1, int(self.settings.digest_background_interval_hours))
            if self._stop.wait(hours * 3600):
                return

    def _tick(self) -> None:
        container = None
        try:
            container = self.container_factory()
            result = container.subscriber_digest.run_due()
            logger.info(
                "Digest run_due: due=%s sent=%s",
                result["subscriber_count"],
                result["sent_count"],
            )
        except Exception:  # noqa: BLE001 — background loop must not die on one tick
            logger.exception("Digest background tick failed")
        finally:
            if container is not None:
                try:
                    container.db.close()
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(0)
