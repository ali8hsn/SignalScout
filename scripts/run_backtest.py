"""Run the backtest and print the pitch report. Run: python scripts/run_backtest.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.container import Container


def main() -> None:
    container = Container()
    report = container.backtest.run()

    print("=" * 64)
    print("SIGNAL SCOUT BACKTEST — pre-breakout signals only")
    print("=" * 64)
    print(f"Threshold (0-100):        {report['threshold']}")
    print(f"Founders in ground truth: {report['founders_total']}")
    print(f"Flagged pre-breakout:     {report['founders_flagged']}  ({report['recall_pct']}%)")
    print(f"Avg lead time:            {report['avg_lead_months']} months")
    print(f"Controls:                 {report['controls_total']}")
    print(f"False positives:          {report['false_positives']}  ({report['false_positive_pct']}%)")
    print(f"Flagged w/ seed edge:     {report['flagged_with_seed_connection']}")
    print("-" * 64)
    print("Most predictive signal types:")
    for row in report["top_signal_types"]:
        print(f"  {row['signal_type']:<24} {row['points']:>7.1f} pts")
    print("-" * 64)
    print(f"{'name':<24}{'score':>7}{'flag':>6}{'lead(mo)':>10}  fellowship")
    for r in report["results"]:
        lead = r["lead_months"] if r["lead_months"] is not None else "-"
        print(f"{r['name']:<24}{r['score']:>7.1f}{'Y' if r['flagged'] else 'n':>6}{str(lead):>10}  {r['fellowship'] or '-'}")


if __name__ == "__main__":
    main()
