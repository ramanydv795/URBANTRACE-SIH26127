from __future__ import annotations

import json
import sys
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


TRAVEL_TIME_FACTOR = 1.75
LOW_SPEED_THRESHOLD_KMH = 10.0


def detect_journey_anomalies() -> list[dict]:
    """
    Detect anomalies from completed real vehicle journeys.

    No synthetic journeys or anomalies are created.
    """

    with engine.begin() as conn:
        journeys = conn.execute(
            text(
                """
                SELECT
                    id,
                    vehicle_id,
                    duration_s,
                    avg_speed_kmh,
                    distance_est_m,
                    camera_count
                FROM vehicle_journeys
                WHERE
                    start_ts IS NOT NULL
                    AND end_ts IS NOT NULL
                    AND duration_s IS NOT NULL
                ORDER BY start_ts
                """
            )
        ).mappings().all()

        if not journeys:
            return []

        # Establish a simple observed baseline.
        durations = [
            float(row["duration_s"])
            for row in journeys
            if row["duration_s"] is not None
            and float(row["duration_s"]) > 0
        ]

        if not durations:
            return []

        baseline_duration = sum(durations) / len(durations)

        results = []

        for journey in journeys:
            duration = (
                float(journey["duration_s"])
                if journey["duration_s"] is not None
                else None
            )

            speed = (
                float(journey["avg_speed_kmh"])
                if journey["avg_speed_kmh"] is not None
                else None
            )

            anomaly_type = None
            reason = None
            confidence = 0.0

            if (
                duration is not None
                and baseline_duration > 0
                and duration > baseline_duration * TRAVEL_TIME_FACTOR
            ):
                anomaly_type = "slow_journey"
                ratio = duration / baseline_duration

                confidence = min(
                    0.99,
                    0.70 + min(0.25, (ratio - TRAVEL_TIME_FACTOR) * 0.20),
                )

                reason = (
                    f"Journey duration {duration:.1f}s is "
                    f"{ratio:.2f}x the observed baseline "
                    f"of {baseline_duration:.1f}s."
                )

            elif speed is not None and speed < LOW_SPEED_THRESHOLD_KMH:
                anomaly_type = "low_speed"
                confidence = min(
                    0.95,
                    0.70
                    + (LOW_SPEED_THRESHOLD_KMH - speed) / 50.0,
                )

                reason = (
                    f"Average journey speed {speed:.1f} km/h "
                    f"is below the {LOW_SPEED_THRESHOLD_KMH:.1f} km/h threshold."
                )

            if anomaly_type is None:
                continue

            evidence = {
                "duration_s": duration,
                "avg_speed_kmh": speed,
                "distance_est_m": (
                    float(journey["distance_est_m"])
                    if journey["distance_est_m"] is not None
                    else None
                ),
                "camera_count": journey["camera_count"],
                "baseline_duration_s": baseline_duration,
                "travel_time_factor": TRAVEL_TIME_FACTOR,
                "low_speed_threshold_kmh": LOW_SPEED_THRESHOLD_KMH,
            }

            existing = conn.execute(
                text(
                    """
                    SELECT id
                    FROM anomalies
                    WHERE
                        journey_id = :journey_id
                        AND type = :type
                    LIMIT 1
                    """
                ),
                {
                    "journey_id": journey["id"],
                    "type": anomaly_type,
                },
            ).first()

            if existing:
                continue

            conn.execute(
                text(
                    """
                    INSERT INTO anomalies
                    (
                        vehicle_id,
                        journey_id,
                        type,
                        reason,
                        evidence,
                        confidence,
                        detected_at
                    )
                    VALUES
                    (
                        :vehicle_id,
                        :journey_id,
                        :type,
                        :reason,
                        CAST(:evidence AS jsonb),
                        :confidence,
                        :detected_at
                    )
                    """
                ),
                {
                    "vehicle_id": journey["vehicle_id"],
                    "journey_id": journey["id"],
                    "type": anomaly_type,
                    "reason": reason,
                    "evidence": json.dumps(evidence),
                    "confidence": confidence,
                    "detected_at": datetime.now(timezone.utc),
                },
            )

            results.append(
                {
                    "journey_id": str(journey["id"]),
                    "vehicle_id": str(journey["vehicle_id"]),
                    "type": anomaly_type,
                    "reason": reason,
                    "confidence": confidence,
                    "evidence": evidence,
                }
            )

        return results