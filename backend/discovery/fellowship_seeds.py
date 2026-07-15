"""Opt-in loading of publicly verified fellowship alumni as expansion seeds."""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from backend.db.repositories.graph_edges import GraphEdgeRepository
from backend.db.repositories.persons import PersonRepository
from backend.domain.graph_edge import GraphEdge
from backend.domain.person import Person


class FellowshipSeedLoader:
    def __init__(
        self,
        persons: PersonRepository,
        edges: GraphEdgeRepository,
        alumni_file: Path,
    ):
        self.persons = persons
        self.edges = edges
        self.alumni_file = alumni_file

    def load(self) -> list[str]:
        """Upsert known alumni, create same-cohort edges, and return GitHub seeds."""
        rows = json.loads(self.alumni_file.read_text()).get("alumni", [])
        members: dict[tuple[str, int], list[tuple[Person, dict]]] = defaultdict(list)
        usernames: list[str] = []
        for row in rows:
            person = (
                self.persons.find_by_github(row.get("github_username"))
                if row.get("github_username")
                else None
            ) or self.persons.find_by_name(row["name"])
            if person is None:
                person = Person(
                    name=row["name"],
                    cohort="seed",
                    github_username=row.get("github_username"),
                    fellowship=f"{row['program']} {row['cohort_year']}",
                )
            person.contact_info.setdefault("fellowship_source_url", row["source_url"])
            self.persons.save(person)
            members[(row["program"], row["cohort_year"])].append((person, row))
            if row.get("github_username") and row["github_username"] not in usernames:
                usernames.append(row["github_username"])

        existing = {
            (
                edge.source_person_id,
                edge.target_person_id,
                edge.metadata.get("program"),
                edge.metadata.get("cohort_year"),
            )
            for edge in self.edges.all()
            if edge.edge_type == "fellowship_cohort"
        }
        observed = datetime.now(timezone.utc).date().isoformat()
        new_edges: list[GraphEdge] = []
        for (program, year), cohort in members.items():
            for index, (source, source_row) in enumerate(cohort):
                for target, target_row in cohort[index + 1 :]:
                    key = (source.id, target.id, program, year)
                    reverse_key = (target.id, source.id, program, year)
                    if key in existing or reverse_key in existing:
                        continue
                    edge = GraphEdge(
                        source_name=source.name,
                        target_name=target.name,
                        edge_type="fellowship_cohort",
                        observed_date=observed,
                        source="curated",
                        metadata={
                            "program": program,
                            "cohort_year": year,
                            "source_urls": [
                                source_row["source_url"],
                                target_row["source_url"],
                            ],
                        },
                    )
                    edge.source_person_id = source.id
                    edge.target_person_id = target.id
                    new_edges.append(edge)
        if new_edges:
            self.edges.save_many(new_edges)
        return usernames
