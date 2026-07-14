"""Live graph expansion from seed accounts (requires GITHUB_TOKEN).
Seeded discoveries are loaded by build_db.py, so this is additive.
Run: GITHUB_TOKEN=... python scripts/run_discovery.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.container import Container
from backend.discovery.graph_expansion import GraphExpander
from backend.scrapers.github_scraper import GithubClient, GithubScraper


def main() -> None:
    container = Container()
    token = container.settings.github_token
    if not token:
        print("GITHUB_TOKEN not set — live discovery skipped (seeded discoveries already loaded).")
        return

    seeds = json.loads(container.settings.seed_accounts_file.read_text())["github_seeds"]
    scraper = GithubScraper(GithubClient(token), [])
    expander = GraphExpander(scraper, container.persons, container.edges)
    discovered = expander.expand(seeds)
    print(f"discovered {len(discovered)} new candidates from {len(seeds)} seeds")

    for person in discovered:
        signals = scraper.scrape_user(person.github_username)
        container.resolver.resolve_signals(signals)
        container.signals.save_many(signals)
        container.contact_enricher.enrich(person, signals)
        container.location_resolver.resolve(person, signals)
        container.persons.save(person)
    container.candidate_service.rescore_all()
    print("scored — review discoveries in the dashboard, then manually verify contacts for digest picks")


if __name__ == "__main__":
    main()
