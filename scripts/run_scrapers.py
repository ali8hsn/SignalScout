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
    people_by_id = {p.id: p for p in people}
    usernames = [p.github_username for p in people]
    display_names = {p.github_username: p.name for p in people}
    scraper = GithubScraper(GithubClient(token), usernames, display_names)

    signals = scraper.scrape()
    container.resolver.resolve_signals(signals)

    # Founders are the backtest ground truth: their scored signals must stay on the
    # curated pre-breakout fixture, never present-day live magnitudes (a single
    # inflated account would skew the pitch metric). We still USE the live scrape
    # to enrich their contacts/locations — we just don't persist it as scored signal.
    scraped_by_person: dict[str, list] = {}
    persisted = []
    for signal in signals:
        person = people_by_id.get(signal.person_id) if signal.person_id else None
        if not person:
            continue
        scraped_by_person.setdefault(person.id, []).append(signal)
        if person.cohort != "founder":
            persisted.append(signal)

    container.signals.save_many(persisted)
    founder_count = sum(1 for p in people if p.cohort == "founder")
    print(
        f"live github: scraped {len(signals)} signals for {len(usernames)} accounts; "
        f"persisted {len(persisted)} (skipped founder scored signals for {founder_count} founders)"
    )

    for person in people:
        if person.cohort == "founder":
            sigs = scraped_by_person.get(person.id, [])  # enrichment only, not persisted
        else:
            sigs = container.signals.for_person(person.id)
        container.contact_enricher.enrich(person, sigs)
        container.location_resolver.resolve(person, sigs)
        container.persons.save(person)
    container.candidate_service.rescore_all()
    print("enrichment + rescore done")


if __name__ == "__main__":
    main()
