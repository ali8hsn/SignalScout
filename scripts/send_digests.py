"""Run due subscriber digests from a Railway cron service or local shell."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.container import Container


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="render previews without sending or recording recipients",
    )
    parser.add_argument(
        "--recipient",
        help="run one active subscriber regardless of frequency/day (useful for manual testing)",
    )
    args = parser.parse_args()

    container = Container()
    try:
        container.db.init_schema()
        result = container.subscriber_digest.run_due(
            dry_run=args.dry_run,
            recipient=args.recipient,
        )
        summary = {
            "dry_run": result["dry_run"],
            "run_at": result["run_at"],
            "subscriber_count": result["subscriber_count"],
            "sent_count": result["sent_count"],
            "statuses": [item["status"] for item in result["results"]],
        }
        print(json.dumps(summary))
    finally:
        container.db.close()


if __name__ == "__main__":
    main()
