"""Regenerate the digest from the current (live) discovery cohort.
Writes out/digest-<date>.html and persists it. Run: python scripts/run_digest.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.container import Container


def main() -> None:
    container = Container()
    digest = container.digest_generator.generate()
    print(f"generated digest with {len(digest.entries)} entries")
    for i, entry in enumerate(digest.entries, 1):
        print(f"  #{i:02d} {entry.name}  (score {entry.score:.0f})")


if __name__ == "__main__":
    main()
