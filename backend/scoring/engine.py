"""ScoringEngine (spec §7.2): raw weighted sum -> diversity/recency/age adjustments.

Every score is decomposable: score_breakdown() returns the itemized receipt
shown in the evidence UI ("USACO Gold 0.7x6.0 = 4.2 ...").
"""

from dataclasses import dataclass
from datetime import date, datetime
from statistics import median

from backend.domain.graph_edge import EDGE_QUALITY, GraphEdge
from backend.domain.person import Person
from backend.domain.signal import Signal
from backend.scoring import weights as W


@dataclass
class ScoreBreakdown:
    raw: float
    items: list[dict]  # [{label, strength, weight, points}]
    diversity_multiplier: float
    recency_bonus: float
    age_factor: float
    adjusted: float


class ScoringEngine:
    def __init__(self, recency_window_days: int = 730):
        self.recency_window_days = recency_window_days

    def connection_signal(
        self, person: Person, edges: list[GraphEdge], seed_ids: set[str], as_of: date
    ) -> Signal | None:
        """Derive a 'connected_to_seeds' signal from graph edges to known seed founders.

        Strength scales with the number of distinct seeds and the quality of the
        best edge type (a co-authorship beats a follow).
        """
        seeds_touched: dict[str, float] = {}
        surfaces_by_seed: dict[str, set[str]] = {}
        latest = None
        for edge in edges:
            if self._parse(edge.observed_date) > as_of:
                continue
            other = None
            if edge.source_person_id in seed_ids and edge.target_person_id == person.id:
                other = edge.source_person_id
            elif edge.target_person_id in seed_ids and edge.source_person_id == person.id:
                other = edge.target_person_id
            if other is None:
                continue
            quality = EDGE_QUALITY.get(edge.edge_type, 0.5)
            if edge.metadata.get("repeat", 0) >= 2 and edge.edge_type in (
                "co_author",
                "hackathon_teammate",
            ):
                quality = 1.0
            # A founder *choosing to follow* someone is a stronger warm signal
            # than a stranger following the founder.
            if edge.edge_type == "github_follows" and edge.metadata.get("direction") == "seed_follows":
                quality = 0.75
            seeds_touched[other] = max(seeds_touched.get(other, 0.0), quality)
            surfaces_by_seed.setdefault(other, set()).add(edge.edge_type)
            if latest is None or edge.observed_date > latest:
                latest = edge.observed_date
        if not seeds_touched:
            return None
        count = len(seeds_touched)
        best_quality = max(seeds_touched.values())
        # Compound independent relationship surfaces for live discoveries only.
        # Founder backtest calibration remains byte-for-byte on the legacy term.
        extra_surfaces = sum(max(0, len(types) - 1) for types in surfaces_by_seed.values())
        surface_bonus = min(0.25, 0.1 * extra_surfaces) if person.cohort == "discovery" else 0.0
        strength = min(1.0, (0.3 + 0.15 * count) * best_quality + 0.1 + surface_bonus)
        distinct_surfaces = sorted({surface for types in surfaces_by_seed.values() for surface in types})
        return Signal(
            person_name=person.name,
            signal_type="connected_to_seeds",
            signal_category="connection",
            signal_date=latest or as_of.isoformat(),
            signal_strength=round(strength, 3),
            source="graph",
            summary=(
                f"Connected to {count} seed founder{'s' if count != 1 else ''} "
                f"across {len(distinct_surfaces)} surface{'s' if len(distinct_surfaces) != 1 else ''} "
                f"(best edge quality {best_quality:.1f})"
            ),
            metadata={
                "seed_count": count,
                "best_quality": best_quality,
                "distinct_surfaces": distinct_surfaces,
                "surface_bonus": round(surface_bonus, 3),
            },
        )

    def compute(self, person: Person, signals: list[Signal], as_of: date) -> ScoreBreakdown:
        items = []
        raw = 0.0
        categories = set()
        recent = 0
        for s in signals:
            sig_date = self._parse(s.signal_date)
            if sig_date > as_of:
                continue
            weight = W.weight_for(s.signal_type)
            points = s.signal_strength * weight
            raw += points
            categories.add(s.signal_category)
            if (as_of - sig_date).days <= self.recency_window_days:
                recent += 1
            items.append({
                "label": s.summary or s.signal_type,
                "signal_type": s.signal_type,
                "strength": s.signal_strength,
                "weight": weight,
                "points": round(points, 2),
                "date": s.signal_date,
                "source": s.source,
                "source_url": s.source_url,
            })

        diversity = 1.0 + W.DIVERSITY_BONUS_PER_CATEGORY * max(0, len(categories) - 1)
        recency_bonus = W.RECENCY_BONUS_PER_SIGNAL * min(recent, W.RECENCY_BONUS_CAP) * raw
        age = W.age_factor(person.graduation_year, as_of.year)
        adjusted = (raw + recency_bonus) * diversity * age
        return ScoreBreakdown(
            raw=round(raw, 2), items=items,
            diversity_multiplier=round(diversity, 2),
            recency_bonus=round(recency_bonus, 2),
            age_factor=age, adjusted=round(adjusted, 2),
        )

    @staticmethod
    def normalize(adjusted_scores: dict[str, float]) -> dict[str, float]:
        """Min-max normalize adjusted scores to 0-100 across the cohort.

        Deprecated for the pitch path: a single dominant account pins itself at
        100 and crushes everyone else. Kept only for callers that explicitly want
        relative-to-max scaling. Prefer `normalize_calibrated`.
        """
        if not adjusted_scores:
            return {}
        top = max(adjusted_scores.values())
        if top <= 0:
            return {k: 0.0 for k in adjusted_scores}
        return {k: round(100.0 * v / top, 1) for k, v in adjusted_scores.items()}

    @staticmethod
    def reference_from(values, top_n: int = 10) -> float:
        """Outlier-robust reference scale: the median of the top-N adjusted scores.

        Using the median of the strong cohort (rather than the single max) means a
        lone outlier 2x above the pack no longer defines 100 — the pack lands at
        ~100 and the field spreads honestly beneath it.
        """
        positive = sorted((v for v in values if v > 0), reverse=True)
        if not positive:
            return 1.0
        top = positive[: max(1, top_n)]
        ref = median(top)
        return ref if ref > 0 else 1.0

    @staticmethod
    def normalize_calibrated(adjusted_scores: dict[str, float], reference: float) -> dict[str, float]:
        """Scale adjusted scores against a fixed reference, capped at 100.

        score = min(100, 100 * adjusted / reference). Because `reference` is a
        stable robust statistic (see `reference_from`), the same call produces
        directly comparable scores across founders, controls, and discoveries —
        a discovery scoring 15 genuinely means '15/100 as founder-like as the
        strong-founder pack'.
        """
        if reference <= 0:
            return {k: 0.0 for k in adjusted_scores}
        return {
            k: round(min(100.0, 100.0 * v / reference), 1)
            for k, v in adjusted_scores.items()
        }

    @staticmethod
    def _parse(iso: str) -> date:
        return datetime.strptime(iso[:10], "%Y-%m-%d").date()
