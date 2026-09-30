"""
URBANTRACE Part 3 - Association Batch Worker

Runs chronological cross-camera vehicle association
for unresolved vehicle observations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make project root importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph_engine.association import run_association


def main() -> None:
    print("URBANTRACE Part 3 - Cross-Camera Association")
    print("=" * 55)

    results = run_association()

    print(f"\nProcessed observations: {len(results)}")

    counts = {}

    for result in results:
        status = result.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1

    print("\nResults:")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    if results:
        print("\nDetailed results:")
        print(
            json.dumps(
                results,
                indent=2,
                default=str,
            )
        )


if __name__ == "__main__":
    main()