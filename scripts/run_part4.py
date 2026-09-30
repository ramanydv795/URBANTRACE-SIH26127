import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from graph_engine.recovery import run_recovery_scan
from graph_engine.journeys import run_journey_aggregation


def main():
    print("=== URBANTRACE PART 4 ===")

    print("\n[1] Missing-trajectory recovery")
    recovery = run_recovery_scan()
    print(f"Recovery candidates: {len(recovery)}")

    print("\n[2] Vehicle journey aggregation")
    journeys = run_journey_aggregation()
    print(f"Journeys finalized: {len(journeys)}")

    print("\nPART 4 BATCH COMPLETE")


if __name__ == "__main__":
    main()