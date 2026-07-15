"""Run the due-subscriber digest job for a Railway cron service."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.container import Container


def main() -> None:
    result = Container().subscriber_digest.run_due(dry_run=False)
    print(
        f"digest cron complete: subscribers={result['subscriber_count']} "
        f"sent={result['sent_count']}"
    )


if __name__ == "__main__":
    main()
