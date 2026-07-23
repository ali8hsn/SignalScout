"""Regression tests for the cleanup/perf/flaw-fix pass: per-IP rate limits on
spend/email/mutation routes, fail-soft /api/health, bounded page_views growth,
and the batch repo loaders that replaced per-person N+1 reads.
"""

import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import build_router
from backend.config import Settings
from backend.container import Container
from backend.domain.graph_edge import GraphEdge
from backend.domain.person import Person
from backend.domain.signal import Signal


class RouterTestBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        settings = Settings(
            db_path=Path(self.temp_dir.name) / "test.db",
            database_url="",
            out_dir=Path(self.temp_dir.name) / "out",
            cron_secret="test-cron-secret",
            discovery_background=False,
        )
        self.container = Container(settings)
        app = FastAPI()
        app.include_router(build_router(self.container))
        self.client = TestClient(app)

    def tearDown(self):
        self.container.db.close()
        self.temp_dir.cleanup()


class RateLimitTests(RouterTestBase):
    def test_send_digest_is_rate_limited(self):
        # Limit is 3/hour: the 4th send from the same client must be rejected
        # with 429 (Resend is unconfigured, so successful sends return previews).
        statuses = [self.client.post("/api/digests/send").status_code for _ in range(4)]
        self.assertEqual(statuses[:3], [200, 200, 200])
        self.assertEqual(statuses[3], 429)

    def test_generate_digest_is_rate_limited(self):
        # Limit is 10/hour.
        statuses = [self.client.post("/api/digests/generate").status_code for _ in range(11)]
        self.assertTrue(all(s == 200 for s in statuses[:10]), statuses)
        self.assertEqual(statuses[10], 429)


class HealthTests(RouterTestBase):
    def test_health_ok(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_health_degrades_instead_of_500(self):
        # Simulate a dead DB: the health handler must catch the error and return
        # 503 degraded rather than letting a 500 bubble out.
        class _BrokenDB:
            backend = "sqlite"

            @property
            def conn(self):
                raise RuntimeError("database is down")

            def close(self):
                pass

        self.container.db = _BrokenDB()
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "degraded")


class PageViewCapTests(RouterTestBase):
    def test_prune_keeps_only_most_recent(self):
        repo = self.container.page_views
        for i in range(20):
            repo.record(f"/p{i}")
        self.assertEqual(repo.count(), 20)
        removed = repo.prune(max_rows=5)
        self.assertEqual(removed, 15)
        self.assertEqual(repo.count(), 5)


class BatchLoaderTests(RouterTestBase):
    def test_for_people_batches_signals_edges_reviews(self):
        a = Person(name="Ada Lovelace", cohort="discovery", score=10)
        b = Person(name="Grace Hopper", cohort="discovery", score=20)
        self.container.persons.save(a)
        self.container.persons.save(b)
        self.container.signals.save(
            Signal(
                person_id=a.id, person_name=a.name, signal_type="competition_win",
                signal_category="competition", signal_date="2026-01-01",
                signal_strength=0.9, source="public_web",
                source_url="https://example.com/a", summary="A win.",
            )
        )
        self.container.edges.save(
            GraphEdge(
                source_name=a.name, target_name=b.name, edge_type="co_author",
                observed_date="2026-01-02", source="seeded",
                source_person_id=a.id, target_person_id=b.id,
            )
        )
        self.container.candidate_review_service.review(a.id, "approved")

        ids = [a.id, b.id]
        sigs = self.container.signals.for_people(ids)
        edges = self.container.edges.for_people(ids)
        reviews = self.container.candidate_reviews.for_people(ids)

        self.assertEqual(len(sigs[a.id]), 1)
        self.assertEqual(sigs[b.id], [])
        # The single a<->b edge appears under both requested endpoints, exactly once.
        self.assertEqual(len(edges[a.id]), 1)
        self.assertEqual(len(edges[b.id]), 1)
        self.assertIn(a.id, reviews)
        self.assertEqual(reviews[a.id].state, "approved")
        self.assertNotIn(b.id, reviews)


if __name__ == "__main__":
    unittest.main()
