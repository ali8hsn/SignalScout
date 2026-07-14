"""Shared founder reference scale.

Both the backtest (pitch metric) and the live discovery ranking normalize
against the SAME reference — the strong-founder pack scored on pre-breakout
evidence only — so every score in the product is on one honest absolute scale.
Kept as a free function (not a method) to avoid a service-to-service dependency.
"""

from datetime import datetime

from backend.db.repositories.graph_edges import GraphEdgeRepository
from backend.db.repositories.persons import PersonRepository
from backend.db.repositories.signals import SignalRepository
from backend.scoring.engine import ScoringEngine


def founder_prebreakout_adjusted(
    persons: PersonRepository,
    signals: SignalRepository,
    edges: GraphEdgeRepository,
    engine: ScoringEngine,
) -> dict[str, float]:
    """Adjusted score for each known founder using ONLY signals dated before their breakout."""
    founders = [p for p in persons.all("founder") if p.breakout_date]
    seed_ids = {p.id for p in founders}
    out: dict[str, float] = {}
    for founder in founders:
        breakout = datetime.strptime(founder.breakout_date[:10], "%Y-%m-%d").date()
        sigs = signals.for_person(founder.id, before=founder.breakout_date)
        person_edges = edges.for_person(founder.id, before=founder.breakout_date)
        conn = engine.connection_signal(founder, person_edges, seed_ids - {founder.id}, breakout)
        if conn:
            sigs = sigs + [conn]
        out[founder.id] = engine.compute(founder, sigs, breakout).adjusted
    return out


def founder_reference(
    persons: PersonRepository,
    signals: SignalRepository,
    edges: GraphEdgeRepository,
    engine: ScoringEngine,
    top_n: int = 10,
) -> float:
    adjusted = founder_prebreakout_adjusted(persons, signals, edges, engine)
    return engine.reference_from(adjusted.values(), top_n=top_n)
