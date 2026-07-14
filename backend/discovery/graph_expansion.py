"""GraphExpander (spec §10): one-hop expansion from seed GitHub accounts.

Live mode (needs GITHUB_TOKEN): for each seed founder, look at BOTH who they
follow (strong warm signal — a founder chose to follow this person) and who
follows them (weaker). Keep only genuinely unknown candidates (not already
famous), and only those with independent evidence on their own profile.
Without a token the pipeline uses the seeded discovery fixtures loaded by
build_db.py — discovery never blocks the demo.
"""

import logging
from datetime import datetime, timezone

from backend.db.repositories.graph_edges import GraphEdgeRepository
from backend.db.repositories.persons import PersonRepository
from backend.domain.graph_edge import GraphEdge
from backend.domain.person import Person
from backend.scrapers.github_scraper import GithubScraper, parse_grad_year

logger = logging.getLogger(__name__)

# Account older than this (years) is assumed established, not pre-breakout.
MAX_ACCOUNT_AGE_YEARS = 13


class GraphExpander:
    def __init__(self, scraper: GithubScraper, persons: PersonRepository, edges: GraphEdgeRepository):
        self.scraper = scraper
        self.persons = persons
        self.edges = edges

    def expand(
        self, seed_usernames: list[str], max_per_seed: int = 60, follower_cap: int = 2000
    ) -> list[Person]:
        """One hop out from each seed, along both follow directions.

        `seed_follows`  = the seed founder follows this person (high-signal).
        `follows_seed`  = this person follows the seed founder (lower-signal).
        A candidate is kept only if unknown (see `_is_unknown`) and has at least
        one independent signal on their own GitHub profile.
        """
        # login -> list[(seed_person, direction)]
        candidate_links: dict[str, list[tuple[Person, str]]] = {}
        for seed in seed_usernames:
            seed_person = self.persons.find_by_github(seed)
            if not seed_person:
                continue
            for direction, users in (
                ("seed_follows", self.scraper.client.following(seed, limit=max_per_seed)),
                ("follows_seed", self.scraper.client.followers(seed, limit=max_per_seed)),
            ):
                for user in users:
                    login = user.get("login")
                    if login:
                        candidate_links.setdefault(login, []).append((seed_person, direction))

        discovered: list[Person] = []
        today = datetime.now(timezone.utc).date().isoformat()
        for login, links in candidate_links.items():
            if self.persons.find_by_github(login):
                continue  # already known (founder or prior discovery)
            profile = self.scraper.client.user(login)
            if not self._is_unknown(profile, follower_cap):
                continue
            signals = self.scraper.scrape_user(login, user=profile)
            if not signals:
                continue  # no independent evidence -> not a candidate (spec §10)

            name = signals[0].person_name
            person = Person(name=name, github_username=login, cohort="discovery")
            person.graduation_year = parse_grad_year(profile.get("bio"))
            person.contact_info["github_followers"] = profile.get("followers", 0)
            person.contact_info["github_created_at"] = profile.get("created_at")
            self.persons.save(person)

            edges = []
            for seed_person, direction in links:
                # edge points source -> target where source follows target
                src, tgt = (seed_person, person) if direction == "seed_follows" else (person, seed_person)
                edge = GraphEdge(
                    source_name=src.name, target_name=tgt.name, edge_type="github_follows",
                    observed_date=today, source="github", metadata={"direction": direction},
                )
                edge.source_person_id = src.id
                edge.target_person_id = tgt.id
                edges.append(edge)
            self.edges.save_many(edges)
            discovered.append(person)
            logger.info("discovered %s (%d seed links)", login, len(links))
        return discovered

    @staticmethod
    def _is_unknown(profile: dict | None, follower_cap: int) -> bool:
        """Filter out orgs/bots and already-famous accounts — we hunt pre-breakout people."""
        if not profile:
            return False
        if profile.get("type") != "User":
            return False
        if profile.get("followers", 0) > follower_cap:
            return False
        created = (profile.get("created_at") or "")[:4]
        if created.isdigit():
            age_years = datetime.now(timezone.utc).year - int(created)
            if age_years > MAX_ACCOUNT_AGE_YEARS:
                return False
        return True
