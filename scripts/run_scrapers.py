"""Run the LIVE GitHub scraper for every person with a github_username.
Requires GITHUB_TOKEN. Without it, the seeded GitHub fixture already covers the demo.
Run: GITHUB_TOKEN=... python scripts/run_scrapers.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.container import Container
from backend.scrapers.github_scraper import GithubClient, GithubScraper


def main() -> None:
    container = Container()
    token = container.settings.github_token
    if not token:
        print("GITHUB_TOKEN not set — skipping live scrape (seeded GitHub signals already loaded).")
        return

    people = [p for p in container.persons.all() if p.github_username and p.cohort != "control"]
    usernames = [p.github_username for p in people]
    display_names = {p.github_username: p.name for p in people}
    scraper = GithubScraper(GithubClient(token), usernames, display_names)

    signals = scraper.scrape()
    container.resolver.resolve_signals(signals)
    container.signals.save_many(signals)
    print(f"live github: {len(signals)} signals for {len(usernames)} accounts")

    for person in people:
        sigs = container.signals.for_person(person.id)
        container.contact_enricher.enrich(person, sigs)
        container.location_resolver.resolve(person, sigs)
        container.persons.save(person)
    container.candidate_service.rescore_all()
    print("enrichment + rescore done")


if __name__ == "__main__":
    main()
