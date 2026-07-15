"""Devpost teammate scraper — no official API, so this parses public HTML
(devpost.com user portfolios and project pages) with stdlib regex only.

Emits `hackathon_win` / `hackathon_finalist` signals and `hackathon_teammate`
edges for discovery-cohort people. Parse defensively: Devpost markup can change
under us, so every failure returns []/None and is never fatal.
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests

from backend.domain.graph_edge import GraphEdge
from backend.domain.person import Person
from backend.domain.signal import Signal

logger = logging.getLogger(__name__)

BASE = "https://devpost.com"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) signal-scout/0.1"

SOFTWARE_LINK_RE = re.compile(r'href="https://devpost\.com/software/([a-z0-9\-_]+)"')
# Text-form profile anchor: <a class="user-profile-link" href="https://devpost.com/user">Name</a>
TEAM_MEMBER_RE = re.compile(
    r'<a class="user-profile-link" href="https://devpost\.com/([A-Za-z0-9_.\-]+)">([^<]+)</a>'
)
OG_TITLE_RE = re.compile(r'<meta property="og:title" content="([^"]*)"')
# One block per hackathon the project was submitted to (inside the Submitted-to aside).
SUBMISSION_RE = re.compile(
    r'<div class="software-list-content">\s*<p>\s*<a href="[^"]*">([^<]+)</a>(.*?)</div>',
    re.DOTALL,
)
WINNER_RE = re.compile(r'class="winner[^"]*"[^>]*>\s*Winner\s*</span>\s*([^<]*)', re.DOTALL)
FINALIST_RE = re.compile(r"\bfinalist\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(20\d{2})\b")


class DevpostScraper:
    """Per-person collection from a public Devpost portfolio. Fail-soft everywhere."""

    name = "devpost"

    def __init__(self, max_projects: int = 3, request_gap_seconds: float = 0.5):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.max_projects = max_projects
        self.request_gap_seconds = request_gap_seconds

    def _get(self, path: str) -> str | None:
        try:
            resp = self.session.get(f"{BASE}{path}", timeout=15)
            if resp.status_code != 200:
                logger.warning("devpost %s -> %s", path, resp.status_code)
                return None
            return resp.text
        except requests.RequestException as exc:
            logger.warning("devpost request failed %s: %s", path, exc)
            return None

    def user_projects(self, username: str) -> list[str]:
        """Project slugs listed on a public portfolio page (order preserved)."""
        html = self._get(f"/{username}")
        if not html:
            return []
        seen: list[str] = []
        for slug in SOFTWARE_LINK_RE.findall(html):
            if slug not in seen:
                seen.append(slug)
        return seen

    def project(self, slug: str) -> dict | None:
        """Parsed project page: title, team (username, display name), submissions."""
        html = self._get(f"/software/{slug}")
        if not html:
            return None
        title_match = OG_TITLE_RE.search(html)
        team: list[tuple[str, str]] = []
        for username, display in TEAM_MEMBER_RE.findall(html):
            entry = (username, display.strip())
            if entry not in team:
                team.append(entry)
        submissions = []
        for hackathon, body in SUBMISSION_RE.findall(html):
            win = WINNER_RE.search(body)
            submissions.append(
                {
                    "hackathon": hackathon.strip(),
                    "won": bool(win),
                    "prize": win.group(1).strip() if win else "",
                    "finalist": bool(FINALIST_RE.search(body)),
                }
            )
        return {
            "slug": slug,
            "title": (title_match.group(1).strip() if title_match else slug),
            "url": f"{BASE}/software/{slug}",
            "team": team,
            "submissions": submissions,
        }

    def collect(self, person: Person, devpost_username: str) -> tuple[list[Signal], list[GraphEdge]]:
        """hackathon_win/hackathon_finalist signals + hackathon_teammate edges.

        Only projects where `devpost_username` appears in the parsed team are
        counted (portfolio pages can also list liked projects).
        """
        slugs = self.user_projects(devpost_username)
        if not slugs:
            return [], []
        today = datetime.now(timezone.utc).date().isoformat()
        signals: list[Signal] = []
        edges: list[GraphEdge] = []
        for slug in slugs[: self.max_projects]:
            time.sleep(self.request_gap_seconds)
            project = self.project(slug)
            if not project:
                continue
            team_logins = {u.lower() for u, _ in project["team"]}
            if devpost_username.lower() not in team_logins:
                continue

            for submission in project["submissions"]:
                date = self._submission_date(submission["hackathon"], today)
                if submission["won"]:
                    prize = f' ("{submission["prize"]}")' if submission["prize"] else ""
                    signals.append(
                        Signal(
                            person_name=person.name, signal_type="hackathon_win",
                            signal_category="hackathon", signal_date=date,
                            signal_strength=0.8, source="devpost",
                            source_url=project["url"],
                            summary=f"Won {submission['hackathon']}{prize} with {project['title']}",
                            raw_data={"slug": slug, "hackathon": submission["hackathon"],
                                      "prize": submission["prize"]},
                        )
                    )
                elif submission["finalist"]:
                    signals.append(
                        Signal(
                            person_name=person.name, signal_type="hackathon_finalist",
                            signal_category="hackathon", signal_date=date,
                            signal_strength=0.6, source="devpost",
                            source_url=project["url"],
                            summary=f"Finalist at {submission['hackathon']} with {project['title']}",
                            raw_data={"slug": slug, "hackathon": submission["hackathon"]},
                        )
                    )

            for teammate_login, teammate_name in project["team"]:
                if teammate_login.lower() == devpost_username.lower():
                    continue
                edges.append(
                    GraphEdge(
                        source_name=person.name, target_name=teammate_name,
                        edge_type="hackathon_teammate",
                        observed_date=self._project_date(project, today),
                        source="devpost",
                        metadata={"project": project["title"],
                                  "devpost_username": teammate_login},
                    )
                )
        return signals, edges

    @staticmethod
    def _submission_date(hackathon: str, fallback: str) -> str:
        """Best-effort event date from a year in the hackathon name."""
        m = YEAR_RE.search(hackathon)
        return f"{m.group(1)}-01-01" if m else fallback

    @staticmethod
    def _project_date(project: dict, fallback: str) -> str:
        for submission in project["submissions"]:
            m = YEAR_RE.search(submission["hackathon"])
            if m:
                return f"{m.group(1)}-01-01"
        return fallback
