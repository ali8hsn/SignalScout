"""BacktestRunner (spec §8) — the pitch.

For every ground-truth founder: keep only signals dated BEFORE their breakout,
recompute the score, and check whether the system would have flagged them.
Controls are scored on their full history to measure false positives.
"""

from collections import defaultdict
from datetime import date, datetime

from backend.db.repositories.graph_edges import GraphEdgeRepository
from backend.db.repositories.persons import PersonRepository
from backend.db.repositories.signals import SignalRepository
from backend.domain.person import Person
from backend.scoring.engine import ScoringEngine


class BacktestRunner:
    def __init__(
        self,
        persons: PersonRepository,
        signals: SignalRepository,
        edges: GraphEdgeRepository,
        engine: ScoringEngine,
        flag_threshold: float,
    ):
        self.persons = persons
        self.signals = signals
        self.edges = edges
        self.engine = engine
        self.flag_threshold = flag_threshold

    def run(self) -> dict:
        founders = [p for p in self.persons.all("founder") if p.breakout_date]
        controls = self.persons.all("control")
        seed_ids = {p.id for p in founders}
        today = date.today()

        founder_adjusted: dict[str, float] = {}
        founder_details: dict[str, dict] = {}
        for founder in founders:
            breakout = self._parse(founder.breakout_date)
            sigs = self.signals.for_person(founder.id, before=founder.breakout_date)
            person_edges = self.edges.for_person(founder.id, before=founder.breakout_date)
            conn = self.engine.connection_signal(founder, person_edges, seed_ids - {founder.id}, breakout)
            if conn:
                sigs = sigs + [conn]
            breakdown = self.engine.compute(founder, sigs, breakout)
            founder_adjusted[founder.id] = breakdown.adjusted
            founder_details[founder.id] = {
                "person": founder, "breakdown": breakdown, "signals": sigs,
                "breakout": breakout, "had_seed_connection": conn is not None,
            }

        control_adjusted: dict[str, float] = {}
        for control in controls:
            sigs = self.signals.for_person(control.id)
            breakdown = self.engine.compute(control, sigs, today)
            control_adjusted[control.id] = breakdown.adjusted

        # Calibrate against the strong-founder pack (median of top-N pre-breakout
        # scores), not the single max, so one outlier can't crush the field.
        reference = self.engine.reference_from(founder_adjusted.values())
        normalized = self.engine.normalize_calibrated(
            {**founder_adjusted, **control_adjusted}, reference
        )

        results = []
        flagged_count = 0
        lead_months_list = []
        signal_type_points: dict[str, float] = defaultdict(float)
        connected_flagged = 0
        for founder in founders:
            detail = founder_details[founder.id]
            score = normalized.get(founder.id, 0.0)
            flagged = score >= self.flag_threshold
            lead_months = None
            if flagged:
                flagged_count += 1
                if detail["had_seed_connection"]:
                    connected_flagged += 1
                crossing = self._first_crossing(detail, normalized[founder.id])
                if crossing:
                    lead_months = round((detail["breakout"] - crossing).days / 30.44, 1)
                    lead_months_list.append(lead_months)
                for item in detail["breakdown"].items:
                    signal_type_points[item["signal_type"]] += item["points"]
            results.append({
                "person_id": founder.id, "name": founder.name,
                "fellowship": founder.fellowship, "breakout_date": founder.breakout_date,
                "score": score, "flagged": flagged, "lead_months": lead_months,
                "signal_count": len(detail["signals"]),
                "had_seed_connection": detail["had_seed_connection"],
            })

        control_scores = [normalized.get(c.id, 0.0) for c in controls]
        false_positives = sum(1 for s in control_scores if s >= self.flag_threshold)
        top_signals = sorted(signal_type_points.items(), key=lambda kv: -kv[1])[:8]

        return {
            "threshold": self.flag_threshold,
            "founders_total": len(founders),
            "founders_flagged": flagged_count,
            "recall_pct": round(100.0 * flagged_count / len(founders), 1) if founders else 0.0,
            "avg_lead_months": round(sum(lead_months_list) / len(lead_months_list), 1) if lead_months_list else None,
            "controls_total": len(controls),
            "false_positives": false_positives,
            "false_positive_pct": round(100.0 * false_positives / len(controls), 1) if controls else 0.0,
            "flagged_with_seed_connection": connected_flagged,
            "founder_scores": sorted((r["score"] for r in results), reverse=True),
            "control_scores": sorted(control_scores, reverse=True),
            "top_signal_types": [{"signal_type": t, "points": round(p, 1)} for t, p in top_signals],
            "results": sorted(results, key=lambda r: -r["score"]),
        }

    def _first_crossing(self, detail: dict, final_score: float) -> date | None:
        """Earliest date the founder's cumulative score reached the flag threshold.

        Re-scores at each signal date using the same normalization scale as the
        final run (final_score / final_adjusted), so 'crossed' means crossed on
        today's scale — conservative and honest.
        """
        breakdown = detail["breakdown"]
        if breakdown.adjusted <= 0:
            return None
        scale = final_score / breakdown.adjusted
        sigs = sorted(detail["signals"], key=lambda s: s.signal_date)
        person: Person = detail["person"]
        for i in range(len(sigs)):
            at = self._parse(sigs[i].signal_date)
            partial = self.engine.compute(person, sigs[: i + 1], at)
            if partial.adjusted * scale >= self.flag_threshold:
                return at
        return None

    @staticmethod
    def _parse(iso: str) -> date:
        return datetime.strptime(iso[:10], "%Y-%m-%d").date()
