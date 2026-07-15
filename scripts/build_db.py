"""Initialize or rebuild the database:
ground truth -> control group -> seeded signals -> discoveries -> edges ->
entity resolution -> enrichment -> scoring.

Run ``python scripts/build_db.py --if-empty`` for hosted startup: it creates the
seed set only when no people exist and never replaces migrated discoveries.
The legacy no-flag command remains an explicit destructive local rebuild.
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.container import Container
from backend.domain.graph_edge import GraphEdge
from backend.domain.person import Person
from backend.domain.signal import Signal
from backend.scrapers.seeded import SeededScraper

CONTROL_COUNT = 60
CONTROL_FIRST = ["Alex", "Jordan", "Taylor", "Casey", "Riley", "Morgan", "Jamie", "Avery",
                 "Quinn", "Cameron", "Devon", "Skyler", "Reese", "Parker", "Emerson"]
CONTROL_LAST = ["Nguyen", "Patel", "Kim", "Garcia", "Chen", "Johnson", "Silva", "Brown",
                "Ali", "Rossi", "Novak", "Tanaka", "Weber", "Lopez", "Murphy"]
CONTROL_SCHOOLS = ["UC Berkeley", "Georgia Tech", "UT Austin", "University of Washington",
                   "Carnegie Mellon University", "NYU", "Columbia University"]


def load_ground_truth(container: Container) -> None:
    data = json.loads(container.settings.ground_truth_file.read_text())
    for row in data["founders"]:
        container.persons.save(Person(
            name=row["name"], cohort="founder",
            github_username=row.get("github_username"),
            twitter_handle=row.get("twitter_handle"),
            school=row.get("school"), graduation_year=row.get("graduation_year"),
            origin_location=row.get("origin_location"),
            current_location=row.get("current_location"),
            fellowship=row.get("fellowship"), breakout_date=row.get("breakout_date"),
            area=row.get("area"), thesis=row.get("thesis"),
        ))
    for row in data.get("seed_researchers", []):
        container.persons.save(Person(
            name=row["name"], cohort="founder", area=row.get("area"),
            notes=row.get("role"),
        ))
    print(f"  loaded {len(data['founders'])} founders + {len(data.get('seed_researchers', []))} researcher anchors")


def load_controls(container: Container) -> None:
    """Deterministic synthetic control group: typical CS students with modest signals."""
    rng = random.Random(42)
    signals = []
    for i in range(CONTROL_COUNT):
        name = f"{rng.choice(CONTROL_FIRST)} {rng.choice(CONTROL_LAST)} (control {i + 1})"
        person = Person(
            name=name, cohort="control",
            school=rng.choice(CONTROL_SCHOOLS),
            graduation_year=rng.choice([2024, 2025, 2026]),
            github_username=f"control-user-{i + 1}",
        )
        container.persons.save(person)
        # Most controls: 0-2 weak signals. A few look stronger — honest false-positive pressure.
        n = rng.choices([0, 1, 2, 3], weights=[25, 40, 25, 10])[0]
        for _ in range(n):
            kind = rng.choice([
                ("github_prolific", "code", 0.5, "Regular contributor"),
                ("hackathon_finalist", "hackathon", 0.4, "Hackathon finalist"),
                ("aime_qualifier", "competition", 0.5, "AIME qualifier"),
                ("github_early_builder", "code", 0.7, "Early GitHub account with projects"),
            ])
            year = rng.choice([2021, 2022, 2023, 2024])
            sig = Signal(
                person_name=name, signal_type=kind[0], signal_category=kind[1],
                signal_date=f"{year}-{rng.randint(1, 12):02d}-15",
                signal_strength=kind[2], source="github" if "github" in kind[0] else "seeded",
                summary=kind[3],
            )
            sig.person_id = person.id
            signals.append(sig)
    container.signals.save_many(signals)
    print(f"  loaded {CONTROL_COUNT} controls with {len(signals)} weak signals")


def load_discoveries(container: Container) -> None:
    """Load the hand-written demo profiles. These are FICTIONAL stand-ins and are
    tagged cohort='demo' so they never mix with real (live-scraped) discoveries.
    Only loaded when build_db is run with --with-demo."""
    path = container.settings.seed_signals_dir / "discoveries.json"
    profiles = json.loads(path.read_text())["profiles"]
    for row in profiles:
        container.persons.save(Person(
            name=row["name"], cohort="demo",
            github_username=row.get("github_username"),
            twitter_handle=row.get("twitter_handle"), email=row.get("email"),
            linkedin_url=row.get("linkedin_url"), personal_site=row.get("personal_site"),
            school=row.get("school"), graduation_year=row.get("graduation_year"),
            origin_location=row.get("origin_location"),
            current_location=row.get("current_location"),
            area=row.get("area"), thesis=row.get("thesis"),
        ))
    print(f"  loaded {len(profiles)} DEMO (fictional) discovery candidates")


def load_signals(container: Container) -> int:
    fixtures = sorted(container.settings.seed_signals_dir.glob("*.json"))
    skip = {"discoveries", "graph_edges"}
    total = 0
    for fixture in fixtures:
        if fixture.stem in skip:
            continue
        scraped = SeededScraper(fixture).scrape()
        container.resolver.resolve_signals(scraped)
        container.signals.save_many(scraped)
        total += len(scraped)
    print(f"  loaded {total} seeded signals from {len(fixtures) - len(skip)} sources")
    return total


def load_edges(container: Container) -> None:
    path = container.settings.seed_signals_dir / "graph_edges.json"
    rows = json.loads(path.read_text())["edges"]
    edges = [GraphEdge(
        source_name=r["source_name"], target_name=r["target_name"],
        edge_type=r["edge_type"], observed_date=r["observed_date"],
        source=r["source"], metadata=r.get("metadata", {}),
    ) for r in rows]
    container.resolver.resolve_edges(edges)
    container.edges.save_many(edges)
    print(f"  loaded {len(edges)} graph edges")


def enrich(container: Container) -> None:
    for person in container.persons.all():
        if person.cohort == "control":
            continue
        sigs = container.signals.for_person(person.id)
        container.contact_enricher.enrich(person, sigs)
        container.location_resolver.resolve(person, sigs)
        container.persons.save(person)
    print("  enrichment pass done (contacts + locations)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the Signal Scout database.")
    parser.add_argument(
        "--with-demo", action="store_true",
        help="Also load the 12 fictional demo discovery profiles (tagged cohort='demo'). "
             "Off by default so only real, live-scraped discoveries appear.",
    )
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="initialize only when the persons table is empty; never reset existing data",
    )
    args = parser.parse_args()

    container = Container()
    container.db.init_schema()
    existing_people = container.db.conn.execute(
        "SELECT COUNT(*) AS count FROM persons"
    ).fetchone()["count"]
    if args.if_empty and existing_people:
        print(
            f"Database already contains {existing_people} people; "
            "leaving all existing and migrated data unchanged."
        )
        container.db.close()
        return
    backend = container.db.backend
    print(f"Building seed set in {backend} database ...")
    if not args.if_empty:
        container.db.reset()
    load_ground_truth(container)
    load_controls(container)
    if args.with_demo:
        load_discoveries(container)
    else:
        print("  skipped fictional demo profiles (run with --with-demo to include them)")
    load_signals(container)
    load_edges(container)
    enrich(container)
    scores = container.candidate_service.rescore_all()
    print(f"  scored {len(scores)} candidates")
    flagged = [p for p in container.persons.all() if (p.score or 0) >= container.settings.flag_threshold
               and p.cohort in ("founder", "discovery")]
    concentrations = container.concentration_detector.compute(flagged)
    print(f"  {len(concentrations)} concentrations detected")
    print("Done.")
    container.db.close()


if __name__ == "__main__":
    main()
