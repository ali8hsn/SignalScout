"""EntityResolver (spec §6): attach raw signals/edges to Person records.

Join keys, in confidence order: github username, then normalized full name.
Ambiguous matches (two persons normalize to the same name) are flagged
needs_review rather than merged. Idempotent — safe to re-run.
"""

import unicodedata

from backend.db.repositories.graph_edges import GraphEdgeRepository
from backend.db.repositories.persons import PersonRepository
from backend.db.repositories.signals import SignalRepository
from backend.domain.graph_edge import GraphEdge
from backend.domain.person import Person
from backend.domain.signal import Signal


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    parts = [p for p in text.lower().replace(".", " ").split() if len(p) > 1]
    if len(parts) > 2:
        parts = [parts[0], parts[-1]]  # strip middle names/initials
    return " ".join(parts)


class EntityResolver:
    def __init__(self, persons: PersonRepository, signals: SignalRepository, edges: GraphEdgeRepository):
        self.persons = persons
        self.signals = signals
        self.edges = edges

    def _index(self) -> tuple[dict[str, Person], dict[str, Person], set[str]]:
        by_name: dict[str, Person] = {}
        by_github: dict[str, Person] = {}
        ambiguous: set[str] = set()
        for person in self.persons.all():
            key = normalize_name(person.name)
            if key in by_name:
                ambiguous.add(key)
            by_name[key] = person
            for alias in person.aliases:
                by_name.setdefault(normalize_name(alias), person)
            if person.github_username:
                by_github[person.github_username.lower()] = person
        return by_name, by_github, ambiguous

    def resolve_signals(self, signals: list[Signal]) -> list[Signal]:
        by_name, by_github, ambiguous = self._index()
        for signal in signals:
            person = self._match(signal.person_name, signal.raw_data.get("login"), by_name, by_github)
            if person:
                signal.person_id = person.id
                key = normalize_name(signal.person_name)
                if key in ambiguous and not person.needs_review:
                    person.needs_review = True
                    self.persons.save(person)
        return signals

    def resolve_edges(self, edges: list[GraphEdge]) -> list[GraphEdge]:
        by_name, by_github, _ = self._index()
        for edge in edges:
            src = self._match(edge.source_name, edge.metadata.get("follower_login"), by_name, by_github)
            dst = self._match(edge.target_name, None, by_name, by_github)
            if src:
                edge.source_person_id = src.id
            if dst:
                edge.target_person_id = dst.id
        return edges

    @staticmethod
    def _match(name: str, github_login: str | None,
               by_name: dict[str, Person], by_github: dict[str, Person]) -> Person | None:
        if github_login and github_login.lower() in by_github:
            return by_github[github_login.lower()]
        return by_name.get(normalize_name(name))
