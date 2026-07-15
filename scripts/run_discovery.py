"""Live graph expansion from seed accounts (requires GITHUB_TOKEN), plus
Semantic Scholar co-author and Devpost teammate enrichment for the discovery
cohort. Seeded discoveries are loaded by build_db.py, so this is additive.

Defaults are scoped small so a run finishes in minutes:
Run: GITHUB_TOKEN=... python scripts/run_discovery.py
     [--seed-limit 3] [--max-per-seed 20] [--scholar-limit 8] [--devpost-limit 8]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.container import Container
from backend.discovery.collab_expansion import CollaborationExpander
from backend.discovery.fellowship_seeds import FellowshipSeedLoader
from backend.discovery.graph_expansion import GraphExpander
from backend.discovery.provider_expansion import ProviderExpander
from backend.domain.graph_edge import GraphEdge
from backend.domain.person import Person
from backend.domain.signal import Signal
from backend.enrichment.budgets import ENRICH, SEARCH
from backend.enrichment.providers.coresignal import CoresignalProvider
from backend.enrichment.providers.pdl import PdlProvider
from backend.scrapers.devpost_scraper import DevpostScraper
from backend.scrapers.github_scraper import GithubClient, GithubScraper
from backend.scrapers.semantic_scholar import SemanticScholarScraper


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scoped live discovery run")
    parser.add_argument("--seed-limit", type=int, default=3,
                        help="seed accounts to expand from (small = minutes, not hours)")
    parser.add_argument("--max-per-seed", type=int, default=20,
                        help="follow-edge candidates pulled per seed, each direction")
    parser.add_argument("--scholar-limit", type=int, default=8,
                        help="discovery people to look up on Semantic Scholar")
    parser.add_argument("--devpost-limit", type=int, default=8,
                        help="discovery people to look up on Devpost (via GitHub username)")
    parser.add_argument("--collab-cap", type=int, default=None,
                        help="maximum unresolved collaborators promoted (default from settings: 15)")
    parser.add_argument("--include-fellowship-seeds", action="store_true",
                        help="opt in to the separate curated fellowship expansion seed pool")
    parser.add_argument("--dry-run", action="store_true",
                        help="source audit only: report per-source plan/counts, spend no credits and write nothing")
    parser.add_argument("--provider-only", action="store_true",
                        help="run only the licensed provider-search lane (no GitHub/Scholar/Devpost)")
    return parser.parse_args()


def save_collected(container: Container, signals: list[Signal], edges: list[GraphEdge]) -> None:
    """Feed new signals/edges through the existing EntityResolver -> repos path."""
    if signals:
        container.resolver.resolve_signals(signals)
        container.signals.save_many(signals)
    if edges:
        container.resolver.resolve_edges(edges)
        container.edges.save_many(edges)


def has_source(container: Container, person: Person, source: str) -> bool:
    """Idempotency guard: skip people already enriched from this source."""
    return any(s.source == source for s in container.signals.for_person(person.id))


def source_audit(container: Container) -> None:
    """Print persisted mix, queue, checkpoints, filters, and budget without writes."""
    counts: dict[str, int] = {}
    people = container.persons.all("discovery")
    origins: dict[str, int] = {}
    for person in people:
        origin = person.discovery_origin or "unknown"
        origins[origin] = origins.get(origin, 0) + 1
        for signal in container.signals.for_person(person.id):
            counts[signal.source] = counts.get(signal.source, 0) + 1
    total = sum(counts.values()) or 1
    print("=" * 56)
    print("SOURCE AUDIT — discovery-cohort signals by source")
    print("=" * 56)
    for source, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {source:<20} {count:>5}  ({100.0 * count / total:.1f}%)")
    print("-" * 56)
    print("discovery origins:")
    for origin, count in sorted(origins.items(), key=lambda item: -item[1]):
        print(f"  {origin:<20} {count:>5}")
    print("-" * 56)
    chain = [provider.name for provider in container.provider_chain]
    print(f"configured provider chain: {' -> '.join(chain) or '(none — no keys)'}")
    for provider in ("pdl", "coresignal"):
        print(
            f"  {provider}: search remaining "
            f"{container.provider_budget.remaining(provider, SEARCH)}, enrich remaining "
            f"{container.provider_budget.remaining(provider, ENRICH)}"
        )
    pending = container.provider_enricher.pending_github_count(people)
    print(f"pending high-priority GitHub enrichments: {pending}")
    filter_config = json.loads(
        container.settings.provider_discovery_filters_file.read_text()
    )
    print("planned allowlisted filters:")
    for provider in ("pdl", "coresignal"):
        labels = [
            filter_set.get("label", "unnamed")
            for filter_set in filter_config.get(f"{provider}_filters", [])
        ]
        print(f"  {provider}: {', '.join(labels) or '(none)'}")

    planning_providers = [
        PdlProvider("dry-run-placeholder"),
        CoresignalProvider("dry-run-placeholder"),
    ]
    planner = ProviderExpander(
        planning_providers,
        container.persons,
        container.provider_identities,
        container.provider_enricher,
        container.provider_budget,
        container.settings.provider_discovery_filters_file,
    )
    result = planner.expand(dry_run=True)
    print("next provider-search pages:")
    if not result.planned_pages:
        print("  (none — filters exhausted or budget unavailable)")
    for page in result.planned_pages:
        print(
            f"  {page['provider']} page={page['next_page']} "
            f"cursor={page['cursor'] or 'start'} size={page['size']} "
            f"filter={page['filter_identity'][:10]} "
            f"{json.dumps(page['filters'], sort_keys=True)}"
        )
    print(
        f"provider search dry-run: {result.attempted} pages planned; "
        "0 API requests, 0 returned records, 0 writes, 0 credits."
    )


def main() -> None:
    args = parse_args()
    container = Container()

    if args.dry_run:
        source_audit(container)
        return

    # LANE 1 (LEAD): provider-search discovery (PDL -> Coresignal). No GitHub
    # account required; budgeted by the search lane. No-op when keyless.
    provider_result = container.provider_expander.expand()
    if container.provider_chain:
        print(f"provider search: created {len(provider_result.created)} people "
              f"(by source {provider_result.source_counts}), "
              f"verified {provider_result.verified}, review {provider_result.review}, "
              f"merged {provider_result.merged}, duplicates {provider_result.duplicates}, "
              f"rejected {provider_result.rejected} {provider_result.rejection_reasons}; "
              f"pages {provider_result.requested_pages}, API requests "
              f"{provider_result.api_requests}, returned records "
              f"{provider_result.returned_records}, conservative credit units "
              f"{provider_result.credit_units}")
    if args.provider_only:
        container.candidate_service.rescore_all()
        print("provider-only run complete — inspect evidence tiers before increasing the cap")
        return

    token = container.settings.github_token
    scraper: GithubScraper | None = None
    discovered: list[Person] = []
    if token:
        seeds = json.loads(container.settings.seed_accounts_file.read_text())["github_seeds"]
        if args.include_fellowship_seeds:
            fellowship = FellowshipSeedLoader(
                container.persons, container.edges, container.settings.fellowship_alumni_file
            )
            seeds.extend(login for login in fellowship.load() if login not in seeds)
        seeds = seeds[: args.seed_limit]
        scraper = GithubScraper(GithubClient(token), [])
        expander = GraphExpander(scraper, container.persons, container.edges)
        discovered = expander.expand(seeds, max_per_seed=args.max_per_seed)
        print(f"discovered {len(discovered)} new candidates from {len(seeds)} seeds")
    else:
        print("GITHUB_TOKEN not set — GitHub lane skipped; Scholar promotion remains available.")

    for person in discovered:
        assert scraper is not None
        signals = scraper.scrape_user(person.github_username)
        container.resolver.resolve_signals(signals)
        container.signals.save_many(signals)
        container.contact_enricher.enrich(person, signals)
        container.location_resolver.resolve(person, signals)
        container.persons.save(person)

    # New-source enrichment: discovery cohort ONLY (founders stay on curated
    # pre-breakout signals — protects the backtest). Fresh discoveries first.
    discovered_ids = {p.id for p in discovered}
    pool = discovered + [p for p in container.persons.all("discovery") if p.id not in discovered_ids]

    scholar = SemanticScholarScraper()
    checked = found = 0
    for person in pool:
        if checked >= args.scholar_limit:
            break
        if not scholar.has_real_name(person) or has_source(container, person, "semantic_scholar"):
            continue
        checked += 1
        signals, edges = scholar.collect(person)
        if signals:
            found += 1
        save_collected(container, signals, edges)
    print(f"semantic scholar: {found}/{checked} people with co-authored papers")

    devpost = DevpostScraper()
    checked = found = 0
    for person in pool:
        if checked >= args.devpost_limit:
            break
        if not person.github_username or has_source(container, person, "devpost"):
            continue
        checked += 1
        signals, edges = devpost.collect(person, person.github_username)
        if signals or edges:
            found += 1
        save_collected(container, signals, edges)
    print(f"devpost: {found}/{checked} people with hackathon footprint")

    collab = CollaborationExpander(
        container.persons,
        container.signals,
        container.edges,
        scraper,
        devpost,
        scholar,
        container.provider_enricher,
    )
    collab_result = collab.expand(
        max_promotions=args.collab_cap or container.settings.collaboration_promotion_cap
    )
    print(
        f"collaboration promotion: {len(collab_result.promoted)}/{collab_result.considered} "
        f"created (by source {collab_result.source_counts})"
    )

    container.candidate_service.rescore_all()
    print("scored — review discoveries in the dashboard, then manually verify contacts for digest picks")


if __name__ == "__main__":
    main()
