"""Backfill licensed enrichment (PDL -> Coresignal) over existing people.

Run: python scripts/run_enrichment.py [--cohort discovery] [--limit N]
                                      [--dry-run] [--provider-chain]

Operational default: up to 100 existing discoveries go through PDL first; only
PDL definitive no-matches fall through to Coresignal (both governed by the
provider-scoped budgets). Discovery-cohort people get merged contacts + new
scored signals; founders get contact fields only (backtest protection).

Safety:
- Keyless: without PDL_API_KEY / CORESIGNAL_API_KEY it prints a notice and exits.
- --dry-run NEVER spends a credit or writes: it reports which people would be
  attempted, served from cache, or skipped for budget.
- Repeat runs reuse the 30-day cache and stop cleanly on budget exhaustion.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.container import Container

DEFAULT_LIMIT = 100  # operational cap: up to 100 existing discoveries per run


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", default="discovery",
                        help="cohort to enrich (default: discovery; founders get contacts only)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"max people to process (default: {DEFAULT_LIMIT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="report the plan without calling providers or spending credits")
    parser.add_argument("--provider-chain", action="store_true",
                        help="print the active provider chain and per-provider budgets, then run")
    args = parser.parse_args()

    container = Container()
    enricher = container.provider_enricher
    settings = container.settings

    chain = [p.name for p in enricher.providers]
    if args.provider_chain or args.dry_run:
        _print_chain(chain, settings)
    if not chain:
        print("No enrichment provider configured (set PDL_API_KEY and/or CORESIGNAL_API_KEY) — nothing to do.")
        return

    people = enricher.prioritize(container.persons.all(args.cohort))
    if args.limit:
        people = people[: args.limit]

    mode = "DRY-RUN (no credits spent)" if args.dry_run else "LIVE"
    print(f"[{mode}] enriching {len(people)} {args.cohort!r} people via chain {chain} (cache TTL 30d)")

    summary = {
        "attempted": 0,
        "matched": 0,
        "cached": 0,
        "fallback": 0,
        "skipped": 0,
        "miss": 0,
        "error": 0,
    }
    new_signal_count = 0
    for person in people:
        outcome = enricher.run(person, dry_run=args.dry_run)
        if outcome.status == "attempted":
            summary["attempted"] += 1
        elif outcome.status == "matched":
            summary["matched"] += 1
            if outcome.fresh_call:
                summary["attempted"] += 1
            if outcome.from_cache:
                summary["cached"] += 1
            if outcome.fallback:
                summary["fallback"] += 1
        elif outcome.status == "skipped":
            summary["skipped"] += 1
        elif outcome.status == "miss":
            summary["miss"] += 1
            if outcome.fresh_call:
                summary["attempted"] += 1
        elif outcome.status == "error":
            summary["error"] += 1

        if not args.dry_run:
            container.persons.save(person)
            new_signal_count += len(outcome.new_signals)
            for s in outcome.new_signals:
                print(f"  + {person.name}: {s.signal_type} [{s.source}] — {s.summary}")

    if new_signal_count and not args.dry_run:
        container.candidate_service.rescore_all()
        print("Rescored all candidates.")

    print("-" * 60)
    print(f"attempted={summary['attempted']}  matched={summary['matched']}  "
          f"cached={summary['cached']}  fallback(coresignal)={summary['fallback']}  "
          f"skipped(budget)={summary['skipped']}  no-match={summary['miss']}  "
          f"errors={summary['error']}")
    if not args.dry_run:
        print(f"new signals: {new_signal_count}")


def _print_chain(chain: list[str], settings) -> None:
    if not chain:
        print("provider chain: (none — no keys configured)")
        return
    search_cap = int(settings.pdl_monthly_cap * settings.pdl_search_split)
    print(f"provider chain: {' -> '.join(chain)}")
    print(f"  pdl: monthly cap {settings.pdl_monthly_cap} "
          f"(search {search_cap} / enrich {settings.pdl_monthly_cap - search_cap}), "
          f"per-run cap {settings.provider_per_run_cap}")
    print(f"  coresignal: daily cap {settings.coresignal_daily_cap} (shared search+fallback)")


if __name__ == "__main__":
    main()
