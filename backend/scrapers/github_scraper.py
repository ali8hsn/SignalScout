"""The only LIVE scraper. Pulls a user's full public GitHub footprint and derives signals.

Requires GITHUB_TOKEN (env). Without a token the pipeline falls back to
data/seed_signals/github_seeded.json so the demo never breaks (locked decision).
"""

import logging
import re
from datetime import datetime, timezone

import requests

from backend.domain.graph_edge import GraphEdge
from backend.domain.signal import Signal
from backend.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

API = "https://api.github.com"

# Bio parsing: signals that a GitHub user is a current student / early-career builder.
STUDENT_KEYWORDS = re.compile(
    r"\b(student|undergrad(?:uate)?|freshman|sophomore|junior|senior|"
    r"high\s?school|hs\s|phd|ph\.d|masters|m\.?sc|b\.?sc|studying|"
    r"class\s+of|incoming|rising|first[-\s]?year|grad\s+student)\b",
    re.IGNORECASE,
)
UNIVERSITY_HINT = re.compile(
    r"\b(mit|stanford|berkeley|cmu|carnegie\s+mellon|caltech|harvard|princeton|"
    r"waterloo|toronto|gatech|georgia\s+tech|nyu|ucla|ucsd|uiuc|uw|"
    r"university|college|institute\s+of\s+technology|\.edu)\b",
    re.IGNORECASE,
)


def parse_grad_year(bio: str | None) -> int | None:
    """Best-effort graduation-year parse from a GitHub bio ('class of 2027', ''27')."""
    if not bio:
        return None
    m = re.search(r"class\s+of\s+(20\d{2})", bio, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"'(2\d)\b", bio)
    if m:
        return 2000 + int(m.group(1))
    m = re.search(r"\b(20[2-3]\d)\s+grad", bio, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def looks_like_student(bio: str | None) -> bool:
    if not bio:
        return False
    return bool(STUDENT_KEYWORDS.search(bio) or UNIVERSITY_HINT.search(bio))


class GithubClient:
    """Thin authenticated wrapper. All failures return None/[] — never fatal."""

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _get(self, path: str, params: dict | None = None):
        try:
            resp = self.session.get(f"{API}{path}", params=params, timeout=15)
            if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
                logger.warning("GitHub rate limit hit on %s", path)
                return None
            if resp.status_code != 200:
                logger.warning("GitHub %s -> %s", path, resp.status_code)
                return None
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("GitHub request failed %s: %s", path, exc)
            return None

    def user(self, username: str) -> dict | None:
        return self._get(f"/users/{username}")

    def repos(self, username: str) -> list[dict]:
        return self._get(f"/users/{username}/repos", {"per_page": 100, "sort": "pushed"}) or []

    def social_accounts(self, username: str) -> list[dict]:
        return self._get(f"/users/{username}/social_accounts") or []

    def following(self, username: str, limit: int = 100) -> list[dict]:
        return (self._get(f"/users/{username}/following", {"per_page": limit}) or [])[:limit]

    def followers(self, username: str, limit: int = 100) -> list[dict]:
        return (self._get(f"/users/{username}/followers", {"per_page": limit}) or [])[:limit]

    def repo_contributors(self, owner: str, repo: str, limit: int = 30) -> list[dict]:
        return (self._get(f"/repos/{owner}/{repo}/contributors", {"per_page": limit}) or [])[:limit]

    def repo_stargazers(self, owner: str, repo: str, limit: int = 20) -> list[dict]:
        """Users who starred a repo. This proves a one-way star, not mutuality."""
        return (self._get(f"/repos/{owner}/{repo}/stargazers", {"per_page": limit}) or [])[:limit]

    def repo_forkers(self, owner: str, repo: str, limit: int = 15) -> list[dict]:
        return (self._get(f"/repos/{owner}/{repo}/forks", {"per_page": limit}) or [])[:limit]

    def repo_issues(self, owner: str, repo: str, limit: int = 20) -> list[dict]:
        """Issue creators and PR authors; GitHub's issues endpoint includes PRs."""
        return (
            self._get(
                f"/repos/{owner}/{repo}/issues",
                {"state": "all", "sort": "updated", "direction": "desc", "per_page": limit},
            )
            or []
        )[:limit]

    def org_members(self, org: str, limit: int = 30) -> list[dict]:
        return (self._get(f"/orgs/{org}/members", {"per_page": limit}) or [])[:limit]

    def user_orgs(self, username: str) -> list[dict]:
        return self._get(f"/users/{username}/orgs") or []


class GithubScraper(BaseScraper):
    name = "github"

    def __init__(self, client: GithubClient, usernames: list[str], display_names: dict[str, str] | None = None):
        self.client = client
        self.usernames = usernames
        self.display_names = display_names or {}

    def scrape(self) -> list[Signal]:
        signals: list[Signal] = []
        for username in self.usernames:
            try:
                signals.extend(self.scrape_user(username))
            except Exception as exc:  # coverage gap, never fatal
                logger.warning("github scrape failed for %s: %s", username, exc)
        return signals

    def scrape_user(self, username: str, user: dict | None = None) -> list[Signal]:
        user = user or self.client.user(username)
        if not user:
            return []
        name = self.display_names.get(username) or user.get("name") or username
        repos = self.client.repos(username)
        socials = self.client.social_accounts(username)
        today = datetime.now(timezone.utc).date().isoformat()

        profile = {
            "login": username,
            "bio": user.get("bio"),
            "location": user.get("location"),
            "email": user.get("email"),
            "blog": user.get("blog"),
            "twitter_username": user.get("twitter_username"),
            "followers": user.get("followers", 0),
            "created_at": user.get("created_at"),
            "social_accounts": socials,
        }

        signals: list[Signal] = []
        created = user.get("created_at", "")[:10]

        # Early builder: account created young relative to today, with real repos
        if created and len(repos) >= 3:
            signals.append(
                Signal(
                    person_name=name, signal_type="github_early_builder", signal_category="code",
                    signal_date=created, signal_strength=0.7, source="github",
                    source_url=user.get("html_url", ""),
                    summary=f"GitHub account since {created[:4]} with {len(repos)}+ public repos",
                    raw_data=profile,
                )
            )

        # Star projects
        for repo in repos:
            stars = repo.get("stargazers_count", 0)
            if stars >= 100:
                strength = 0.9 if stars >= 1000 else 0.6
                signals.append(
                    Signal(
                        person_name=name, signal_type="github_star_project", signal_category="code",
                        signal_date=(repo.get("created_at") or today)[:10],
                        signal_strength=strength, source="github",
                        source_url=repo.get("html_url", ""),
                        summary=f"{repo['name']}: {stars:,} stars",
                        raw_data={"stars": stars, "language": repo.get("language"),
                                  "forks": repo.get("forks_count", 0)},
                    )
                )

        # Prolific: many repos as a proxy (contribution calendar needs GraphQL; keep it simple)
        if len(repos) >= 30:
            signals.append(
                Signal(
                    person_name=name, signal_type="github_prolific", signal_category="code",
                    signal_date=today, signal_strength=0.5, source="github",
                    source_url=user.get("html_url", ""),
                    summary=f"{len(repos)}+ public repos, sustained output",
                    raw_data=profile,
                )
            )

        # Student / early-career builder: bio says they are currently in school.
        bio = user.get("bio") or ""
        if looks_like_student(bio):
            signals.append(
                Signal(
                    person_name=name, signal_type="student_builder", signal_category="education",
                    signal_date=today, signal_strength=0.7, source="github",
                    source_url=user.get("html_url", ""),
                    summary=f'Bio reads as a current student/early builder: "{bio[:90]}"',
                    raw_data=profile,
                )
            )
        return signals

    def follow_edges(self, username: str, name: str) -> list[GraphEdge]:
        """Edges from this user's followers (follower -> user)."""
        today = datetime.now(timezone.utc).date().isoformat()
        edges = []
        for follower in self.client.followers(username):
            edges.append(
                GraphEdge(
                    source_name=follower["login"], target_name=name,
                    edge_type="github_follows", observed_date=today, source="github",
                    metadata={"follower_login": follower["login"]},
                )
            )
        return edges
