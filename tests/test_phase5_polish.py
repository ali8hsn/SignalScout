import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import build_router
from backend.config import Settings
from backend.container import Container

ROOT = Path(__file__).resolve().parent.parent


class Phase5PolishTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.settings = Settings(
            db_path=root / "test.db",
            database_url="",
            out_dir=root / "out",
        )
        self.container = Container(self.settings)
        self.container.db.init_schema()

    def tearDown(self):
        self.container.db.close()
        self.temp_dir.cleanup()

    def test_page_view_endpoint_stores_only_minimal_fields(self):
        app = FastAPI()
        app.include_router(build_router(self.container))
        client = TestClient(app)

        response = client.post(
            "/api/analytics/page-view",
            json={"path": "/discover", "referrer": "https://example.com/intro"},
        )

        self.assertEqual(response.status_code, 202)
        row = self.container.db.conn.execute("SELECT * FROM page_views").fetchone()
        self.assertEqual(row["path"], "/discover")
        self.assertEqual(row["referrer"], "https://example.com/intro")
        self.assertEqual(set(row.keys()), {"id", "path", "viewed_at", "referrer"})

    def test_page_view_rejects_absolute_external_urls(self):
        app = FastAPI()
        app.include_router(build_router(self.container))
        client = TestClient(app)
        response = client.post(
            "/api/analytics/page-view",
            json={"path": "https://tracker.example/path"},
        )
        self.assertEqual(response.status_code, 422)

    def test_if_empty_seed_does_not_replace_existing_people(self):
        db_path = Path(self.temp_dir.name) / "hosted.db"
        env = {**os.environ, "SIGNAL_SCOUT_DB": str(db_path), "DATABASE_URL": ""}
        command = [sys.executable, "scripts/build_db.py", "--if-empty"]

        subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=True, text=True)
        with closing(sqlite3.connect(db_path)) as conn:
            initial = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
            conn.execute(
                """INSERT INTO persons
                   (id, name, cohort, aliases, contact_info, needs_review)
                   VALUES ('real-discovery', 'Real Discovery', 'discovery', '[]', '{}', 0)"""
            )
            conn.commit()

        subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=True, text=True)
        with closing(sqlite3.connect(db_path)) as conn:
            final = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
            preserved = conn.execute(
                "SELECT name FROM persons WHERE id = 'real-discovery'"
            ).fetchone()
        self.assertGreater(initial, 0)
        self.assertEqual(final, initial + 1)
        self.assertEqual(preserved[0], "Real Discovery")


if __name__ == "__main__":
    unittest.main()
