import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import build_router
from backend.config import Settings
from backend.container import Container
from backend.domain.person import Person
from backend.domain.signal import Signal


class PublicReleaseSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        settings = Settings(
            db_path=Path(self.temp_dir.name) / "test.db",
            database_url="",
            out_dir=Path(self.temp_dir.name) / "out",
            environment="production",
            admin_secret="test-admin-secret",
            cron_secret="test-cron-secret",
            public_base_url="https://testserver",
        )
        self.container = Container(settings)
        app = FastAPI()
        app.include_router(build_router(self.container))
        self.client = TestClient(app)
        self.admin_headers = {"Authorization": "Bearer test-admin-secret"}

    def tearDown(self):
        self.container.db.close()
        self.temp_dir.cleanup()

    def test_candidate_browsing_is_public_but_operator_routes_are_gated(self):
        self.assertEqual(self.client.get("/api/candidates").status_code, 200)
        self.assertEqual(self.client.get("/api/overview").status_code, 200)
        for method, path in (
            ("post", "/api/discovery/run"),
            ("get", "/api/discovery/status"),
            ("get", "/api/digest/preview"),
            ("get", "/api/candidate-reviews"),
            ("post", "/api/digests/generate"),
        ):
            response = getattr(self.client, method)(path)
            self.assertEqual(response.status_code, 401, path)

    def test_admin_bearer_allows_preview_without_recording_send(self):
        person = Person(
            name="Reviewed Candidate",
            cohort="discovery",
            score=50,
            github_username="reviewed",
        )
        self.container.persons.save(person)
        self.container.signals.save(
            Signal(
                person_id=person.id,
                person_name=person.name,
                signal_type="competition_win",
                signal_category="competition",
                signal_date="2026-01-01",
                signal_strength=0.9,
                source="public_web",
                source_url="https://example.com/evidence",
                summary="Won a documented public competition.",
            )
        )
        self.container.candidate_review_service.review(
            person.id,
            "approved",
            why_now="Won a documented public competition while shipping a public project.",
            source_bucket="manual_public",
            contactable=True,
            primary_evidence_url="https://example.com/evidence",
            reviewer="test",
        )
        subscriber = self.container.subscribers.subscribe(
            "owner@example.com", "weekly", {}
        )
        response = self.client.get(
            "/api/digest/preview?email=owner@example.com",
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [candidate["id"] for candidate in response.json()["candidates"]],
            [person.id],
        )
        self.assertEqual(self.container.digest_sends.sent_person_ids(subscriber.id), set())

    def test_public_signup_does_not_expose_action_token(self):
        response = self.client.post(
            "/api/subscribers",
            json={"email": "reader@example.com", "frequency": "weekly"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("subscriber_token", response.json())

    def test_production_operator_configuration_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "ADMIN_SECRET"):
            Container(
                Settings(
                    db_path=Path(self.temp_dir.name) / "bad.db",
                    database_url="",
                    environment="production",
                    admin_secret="",
                    cron_secret="",
                )
            )


if __name__ == "__main__":
    unittest.main()
