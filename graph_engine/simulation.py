from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings


engine = create_engine(
    get_settings().sync_database_url,
    pool_pre_ping=True,
)


def run_simulation(
    name: str,
    scenario_type: str,
    params: dict,
    created_by: str = "system",
) -> dict:
    """
    Run a topology-aware what-if simulation.

    No real traffic observations are modified.
    """

    affected_road_ids = params.get("affected_road_ids", [])

    if not isinstance(affected_road_ids, list):
        raise ValueError("affected_road_ids must be a list")

    with engine.begin() as conn:
        valid_roads = []

        if affected_road_ids:
            rows = conn.execute(
                text(
                    """
                    SELECT id
                    FROM roads
                    WHERE id = ANY(:road_ids)
                    """
                ),
                {
                    "road_ids": affected_road_ids,
                },
            ).fetchall()

            valid_roads = [row.id for row in rows]

        before_metrics = {
            "affected_road_count": len(valid_roads),
            "observed_trip_count": 0,
        }

        after_metrics = {
            "affected_road_count": len(valid_roads),
            "estimated_delay_factor": (
                1.25 if valid_roads else 1.0
            ),
            "scenario_type": scenario_type,
        }

        scenario_id = uuid.uuid4()

        conn.execute(
            text(
                """
                INSERT INTO simulation_scenarios
                (
                    id,
                    name,
                    type,
                    params,
                    created_by
                )
                VALUES
                (
                    :id,
                    :name,
                    :type,
                    CAST(:params AS jsonb),
                    :created_by
                )
                """
            ),
            {
                "id": scenario_id,
                "name": name,
                "type": scenario_type,
                "params": json.dumps(params),
                "created_by": created_by,
            },
        )

        result_id = uuid.uuid4()

        conn.execute(
            text(
                """
                INSERT INTO simulation_results
                (
                    id,
                    scenario_id,
                    before_metrics,
                    after_metrics,
                    affected_road_ids
                )
                VALUES
                (
                    :id,
                    :scenario_id,
                    CAST(:before_metrics AS jsonb),
                    CAST(:after_metrics AS jsonb),
                    :affected_road_ids
                )
                """
            ),
            {
                "id": result_id,
                "scenario_id": scenario_id,
                "before_metrics": json.dumps(before_metrics),
                "after_metrics": json.dumps(after_metrics),
                "affected_road_ids": valid_roads,
            },
        )

        return {
            "scenario_id": str(scenario_id),
            "result_id": str(result_id),
            "name": name,
            "type": scenario_type,
            "affected_road_ids": valid_roads,
            "before_metrics": before_metrics,
            "after_metrics": after_metrics,
        }