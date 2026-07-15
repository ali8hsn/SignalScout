"""Backfill licensed enrichment (PDL / Coresignal) over existing people.

Run: python scripts/run_enrichment.py [--cohort discovery] [--limit N]

Graceful keyless: without PDL_API_KEY / CORESIGNAL_API_KEY it prints a notice
and exits cleanly. Discovery-cohort people get merged contacts + new scored
signals; founders get contact fields only (backtest protection). Respects the
30-day enrichment_cache and DAILY_ENRICHMENT_BUDGET.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.container import Container


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", default="discovery",
                        help="cohort to enrich (default: discovery; founders get contacts only)")
    parser.add_argument("--limit", type=int, default=None, help="max people to process")
    args = parser.parse_args()

    container = Container()
    enricher = container.provider_enricher
    if enricher.provider is None:
        print("No enrichment provider configured (set ENRICHMENT_PROVIDER + its API key) — nothing to do.")
        return

    people = container.persons.all(args.cohort)
    if args.limit:
        people = people[: args.limit]
    print(f"Enriching {len(people)} {args.cohort!r} people via {enricher.provider.name} "
          f"(budget {container.settings.daily_enrichment_budget}/day, cache TTL 30d)")

    enriched = 0
    new_signal_count = 0
    for person in people:
        new_signals = enricher.enrich(person)
        container.persons.save(person)
        if new_signals or person.contact_info.get("enriched_by"):
            enriched += 1
        new_signal_count += len(new_signals)
        for s in new_signals:
            print(f"  + {person.name}: {s.signal_type} — {s.summary}")

    if new_signal_count:
        container.candidate_service.rescore_all()
        print("Rescored all candidates.")
    print(f"Done: {enriched}/{len(people)} people touched, {new_signal_count} new signals.")


if __name__ == "__main__":
    main()
