"""DiscoveryJobManager: runs the live discovery pipeline in a background thread
and exposes in-memory stage progress for polling.

Single global job (a `threading.Lock` guards start + state). The pipeline maps to
four stages the UI animates: Scrape -> Resolve -> Enrich -> Score. The worker
builds its OWN Container (its own SQLite connection) so its writes never collide
with the API's read connection; the status endpoint only ever touches in-memory
state, so polling stays cheap and DB-free.
"""

import copy
import json
import logging
import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from backend.config import Settings
from backend.discovery.graph_expansion import GraphExpander
from backend.scrapers.github_scraper import GithubClient, GithubScraper

if TYPE_CHECKING:  # avoid a Container <-> DiscoveryJobManager import cycle
    from backend.container import Container

logger = logging.getLogger(__name__)

STAGES = ("scrape", "resolve", "enrich", "score")


class DiscoveryJobManager:
    def __init__(self, settings: Settings, container_factory: "Callable[[], Container]"):
        self.settings = settings
        self._container_factory = container_factory
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._state = self._idle_state()

    @staticmethod
    def _idle_state() -> dict:
        return {
            "job_id": None,
            "state": "idle",  # idle | running | done | error
            "stages": [{"name": name, "status": "pending", "count": 0} for name in STAGES],
            "discovered_count": 0,
            "started_at": None,
            "finished_at": None,
            "error": None,
        }

    def status(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._state)

    def start(self) -> str:
        """Begin a scoped background run. Raises RuntimeError if one is already
        running (-> 409) or ValueError if GITHUB_TOKEN is unset (-> 400)."""
        with self._lock:
            if self._state["state"] == "running":
                raise RuntimeError("a discovery run is already in progress")
            if not self.settings.github_token:
                raise ValueError("GITHUB_TOKEN is not set — start the API with a token to run live discovery")
            job_id = uuid.uuid4().hex[:12]
            self._state = self._idle_state()
            self._state.update(
                job_id=job_id,
                state="running",
                started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            self._thread = threading.Thread(target=self._run, args=(job_id,), daemon=True)
            self._thread.start()
            return job_id

    def _resolve_seeds(self, container: "Container") -> list[str]:
        """Prefer curated `demo_seeds` (young, dense-orbit prior discoveries) that
        actually exist in this DB; fall back to the founder `github_seeds`. Sliced
        to `discovery_seed_limit` to keep an on-camera run short."""
        data = json.loads(self.settings.seed_accounts_file.read_text())
        demo = [s for s in data.get("demo_seeds", []) if container.persons.find_by_github(s)]
        seeds = demo or data["github_seeds"]
        return seeds[: self.settings.discovery_seed_limit]

    def _set_stage(self, name: str, status: str | None = None, count: int | None = None) -> None:
        with self._lock:
            for stage in self._state["stages"]:
                if stage["name"] == name:
                    if status is not None:
                        stage["status"] = status
                    if count is not None:
                        stage["count"] = count
                    break

    def _run(self, job_id: str) -> None:
        container: "Container | None" = None
        try:
            container = self._container_factory()
            token = self.settings.github_token
            seeds = self._resolve_seeds(container)

            scraper = GithubScraper(GithubClient(token), [])
            expander = GraphExpander(scraper, container.persons, container.edges)

            self._set_stage("scrape", status="active")

            def on_progress(stage: str, count: int) -> None:
                self._set_stage(stage, status="active", count=count)

            discovered = expander.expand(
                seeds,
                max_per_seed=self.settings.discovery_max_per_seed,
                on_progress=on_progress,
                # tight collab caps: keep the scoped on-camera run short
                repos_per_seed=2,
                contributors_per_repo=15,
                org_members_per_seed=15,
            )
            self._set_stage("scrape", status="done")
            self._set_stage("resolve", status="done", count=len(discovered))

            self._set_stage("enrich", status="active")
            for i, person in enumerate(discovered, start=1):
                signals = scraper.scrape_user(person.github_username)
                container.resolver.resolve_signals(signals)
                container.signals.save_many(signals)
                container.contact_enricher.enrich(person, signals)
                container.location_resolver.resolve(person, signals)
                container.provider_enricher.enrich(person)  # licensed data; no-op keyless
                container.persons.save(person)
                self._set_stage("enrich", count=i)
            self._set_stage("enrich", status="done", count=len(discovered))

            self._set_stage("score", status="active")
            container.candidate_service.rescore_all()
            self._set_stage("score", status="done")

            with self._lock:
                self._state["state"] = "done"
                self._state["discovered_count"] = len(discovered)
                self._state["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        except Exception as exc:  # noqa: BLE001 - surface any failure to the poller
            logger.exception("discovery job %s failed", job_id)
            with self._lock:
                self._state["state"] = "error"
                self._state["error"] = str(exc)
                self._state["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                for stage in self._state["stages"]:
                    if stage["status"] == "active":
                        stage["status"] = "error"
        finally:
            if container is not None:
                container.db.close()
