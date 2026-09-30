from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
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


def build_od_matrix() -> list[dict]:
    """
    Build daily OD matrix from completed vehicle journeys.

    Only journeys with both origin and destination zones are included.
    No synthetic trips are created.
    """

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    DATE(start_ts) AS date,
                    start_zone_id AS origin_zone_id,
                    end_zone_id AS dest_zone_id,
                    COUNT(*) AS trip_count
                FROM vehicle_journeys
                WHERE
                    start_ts IS NOT NULL
                    AND end_ts IS NOT NULL
                    AND start_zone_id IS NOT NULL
                    AND end_zone_id IS NOT NULL
                GROUP BY
                    DATE(start_ts),
                    start_zone_id,
                    end_zone_id
                ORDER BY
                    DATE(start_ts),
                    start_zone_id,
                    end_zone_id
                """
            )
        ).mappings().all()

        results = []

        for row in rows:
            existing = conn.execute(
                text(
                    """
                    SELECT id
                    FROM od_matrix_daily
                    WHERE
                        date = :date
                        AND origin_zone_id = :origin_zone_id
                        AND dest_zone_id = :dest_zone_id
                    """
                ),
                {
                    "date": row["date"],
                    "origin_zone_id": row["origin_zone_id"],
                    "dest_zone_id": row["dest_zone_id"],
                },
            ).first()

            if existing:
                conn.execute(
                    text(
                        """
                        UPDATE od_matrix_daily
                        SET trip_count = :trip_count
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": existing.id,
                        "trip_count": row["trip_count"],
                    },
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO od_matrix_daily
                        (
                            date,
                            origin_zone_id,
                            dest_zone_id,
                            trip_count
                        )
                        VALUES
                        (
                            :date,
                            :origin_zone_id,
                            :dest_zone_id,
                            :trip_count
                        )
                        """
                    ),
                    {
                        "date": row["date"],
                        "origin_zone_id": row["origin_zone_id"],
                        "dest_zone_id": row["dest_zone_id"],
                        "trip_count": row["trip_count"],
                    },
                )

            results.append(dict(row))

        return results


def detect_bottlenecks() -> list[dict]:
    """
    Detect road/intersection bottlenecks from observed camera transitions.

    Uses actual transition counts and estimated travel time.
    No bottleneck is created when there is no observed traffic.
    """

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    ct.id,
                    ct.from_observation_id,
                    ct.to_observation_id,
                    ct.travel_time_s,
                    ct.est_speed_kmh,
                    ct.confidence,
                    c1.id AS from_camera_id,
                    c2.id AS to_camera_id
                FROM camera_transitions ct
                JOIN vehicle_observations o1
                    ON o1.id = ct.from_observation_id
                JOIN vehicle_observations o2
                    ON o2.id = ct.to_observation_id
                JOIN cameras c1
                    ON c1.id = o1.camera_id
                JOIN cameras c2
                    ON c2.id = o2.camera_id
                WHERE
                    ct.status = 'auto_linked'
                """
            )
        ).mappings().all()

        if not rows:
            return []

        grouped = defaultdict(list)

        for row in rows:
            key = (row["from_camera_id"], row["to_camera_id"])
            grouped[key].append(row)

        results = []

        for (from_camera_id, to_camera_id), transitions in grouped.items():
            count = len(transitions)

            travel_times = [
                float(x["travel_time_s"])
                for x in transitions
                if x["travel_time_s"] is not None
            ]

            speeds = [
                float(x["est_speed_kmh"])
                for x in transitions
                if x["est_speed_kmh"] is not None
            ]

            avg_travel_time = (
                sum(travel_times) / len(travel_times)
                if travel_times
                else None
            )

            avg_speed = (
                sum(speeds) / len(speeds)
                if speeds
                else None
            )

            # Conservative thresholds.
            # A bottleneck requires actual observed traffic.
            severity = None

            if count >= 20:
                severity = "high"
            elif count >= 10:
                severity = "medium"
            elif count >= 5:
                severity = "low"

            if severity is None:
                continue

            explanation = (
                f"Observed {count} vehicle transitions between "
                f"camera {from_camera_id} and camera {to_camera_id}."
            )

            indicators = {
                "transition_count": count,
                "avg_travel_time_s": avg_travel_time,
                "avg_speed_kmh": avg_speed,
                "from_camera_id": from_camera_id,
                "to_camera_id": to_camera_id,
            }

            # We need an actual intersection/road reference.
            # Use topology to map the camera pair to a road path.
            topology = conn.execute(
                text(
                    """
                    SELECT road_path_ids
                    FROM camera_topology
                    WHERE
                        from_camera_id = :from_camera_id
                        AND to_camera_id = :to_camera_id
                    LIMIT 1
                    """
                ),
                {
                    "from_camera_id": from_camera_id,
                    "to_camera_id": to_camera_id,
                },
            ).first()

            if not topology or not topology.road_path_ids:
                continue

            road_ids = list(topology.road_path_ids)

            road_id = road_ids[0]

            intersection = conn.execute(
                text(
                    """
                    SELECT id
                    FROM intersections
                    WHERE
                        id IN (
                            SELECT intersection_id
                            FROM roads
                            WHERE id = :road_id
                        )
                    LIMIT 1
                    """
                ),
                {"road_id": road_id},
            ).first()

            intersection_id = intersection.id if intersection else None

            # Avoid duplicate active records for the same road.
            existing = conn.execute(
                text(
                    """
                    SELECT id
                    FROM bottlenecks
                    WHERE
                        road_id = :road_id
                        AND severity = :severity
                    ORDER BY detected_at DESC
                    LIMIT 1
                    """
                ),
                {
                    "road_id": road_id,
                    "severity": severity,
                },
            ).first()

            if existing:
                continue

            conn.execute(
                text(
                    """
                    INSERT INTO bottlenecks
                    (
                        intersection_id,
                        road_id,
                        detected_at,
                        indicators,
                        explanation,
                        severity
                    )
                    VALUES
                    (
                        :intersection_id,
                        :road_id,
                        :detected_at,
                        CAST(:indicators AS jsonb),
                        :explanation,
                        :severity
                    )
                    """
                ),
                {
                    "intersection_id": intersection_id,
                    "road_id": road_id,
                    "detected_at": datetime.now(timezone.utc),
                    "indicators": json.dumps(indicators),
                    "explanation": explanation,
                    "severity": severity,
                },
            )

            results.append(
                {
                    "road_id": road_id,
                    "intersection_id": intersection_id,
                    "severity": severity,
                    "indicators": indicators,
                }
            )

        return results


def run_traffic_analysis() -> dict:
    od = build_od_matrix()
    bottlenecks = detect_bottlenecks()

    return {
        "od_matrix_rows": len(od),
        "bottlenecks_detected": len(bottlenecks),
        "od_matrix": od,
        "bottlenecks": bottlenecks,
    }