"""GraphExpander (spec §10): one-hop expansion from seed GitHub accounts.

Live mode (needs GITHUB_TOKEN): pull followers/following of seed accounts,
keep unknowns that have independent evidence, emit persons + edges.
Without a token the pipeline uses the seeded discovery fixtures loaded by
build_db.py — discovery never blocks the demo.
"""

import logging

from backend.db.repositories.graph_edges import GraphEdgeRepository
from backend.db.repositories.persons import PersonRepository
from backend.domain.graph_edge import GraphEdge
from backend.domain.person import Person
from backend.scrapers.github_scraper import GithubScraper

logger = logging.getLogger(__name__)


class GraphExpander:
    def __init__(self, scraper: GithubScraper, persons: PersonRepository, edges: GraphEdgeRepository):
        self.scraper = scraper
        self.persons = persons
        self.edges = edges

    def expand(self, seed_usernames: list[str], max_new_per_seed: int = 25) -> list[Person]:
        """One hop out from each seed. A follower becomes a discovery candidate only
        if their own GitHub profile shows independent evidence (signals)."""
        discovered: list[Person] = []
        for seed in seed_usernames:
            seed_person = self.persons.find_by_github(seed)
            if not seed_person:
                continue
            followers = self.scraper.client.followers(seed, limit=max_new_per_seed)
            for follower in followers:
                login = follower["login"]
                if self.persons.find_by_github(login):
                    continue  # already known
                signals = self.scraper.scrape_user(login)
                if not signals:
                    continue  # no independent evidence -> not a candidate (spec §10)
                name = signals[0].person_name
                person = Person(name=name, github_username=login, cohort="discovery")
                self.persons.save(person)
                edge = GraphEdge(
                    source_name=seed_person.name, target_name=name,
                    edge_type="github_follows", observed_date=signals[0].signal_date,
                    source="github", metadata={"seed": seed},
                )
                edge.source_person_id = seed_person.id
                edge.target_person_id = person.id
                self.edges.save_many([edge])
                discovered.append(person)
                logger.info("discovered %s via %s", login, seed)
        return discovered
