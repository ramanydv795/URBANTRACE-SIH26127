"""
URBANTRACE Part 4.3 - Vehicle Journey Aggregation

Closes finished vehicle journeys after an idle timeout and stores
aggregated journey metrics in vehicle_journeys.

No fake data is created.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import create_engine, text

from app.config import get_settings


IDLE_TIMEOUT_S = 15 * 60


class VehicleJourneyAggregator:
    def __init__(self, idle_timeout_s: int = IDLE_TIMEOUT_S) -> None:
        settings = get_settings()

        self.engine = create_engine(
            settings.sync_database_url,
            pool_pre_ping=True,
        )

        self.idle_timeout_s = idle_timeout_s

    def _get_finished_vehicles(self) -> list[dict[str, Any]]:
        """
        Find vehicles whose latest observation is older than
        the configured idle timeout.
        """

        cutoff = datetime.utcnow() - timedelta(
            seconds=self.idle_timeout_s
        )

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        v.id AS vehicle_id,
                        MAX(vo.ts) AS last_seen
                    FROM vehicles v
                    JOIN vehicle_observations vo
                        ON vo.vehicle_id = v.id
                    GROUP BY v.id
                    HAVING MAX(vo.ts) <= :cutoff
                    ORDER BY MAX(vo.ts)
                    """
                ),
                {"cutoff": cutoff},
            ).mappings().all()

        return [dict(row) for row in rows]

    def _get_observations(
        self,
        vehicle_id: UUID,
    ) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        vo.id,
                        vo.camera_id,
                        c.code AS camera_code,
                        c.zone_id,
                        vo.ts,
                        vo.plate_text,
                        vo.plate_conf,
                        vo.detection_conf
                    FROM vehicle_observations vo
                    JOIN cameras c
                        ON c.id = vo.camera_id
                    WHERE vo.vehicle_id = :vehicle_id
                    ORDER BY vo.ts ASC
                    """
                ),
                {"vehicle_id": str(vehicle_id)},
            ).mappings().all()

        return [dict(row) for row in rows]

    def _get_transition_distance(
        self,
        from_camera_id: int,
        to_camera_id: int,
    ) -> float:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT distance_m
                    FROM camera_topology
                    WHERE from_camera_id = :from_camera_id
                      AND to_camera_id = :to_camera_id
                    ORDER BY typical_travel_s
                    LIMIT 1
                    """
                ),
                {
                    "from_camera_id": from_camera_id,
                    "to_camera_id": to_camera_id,
                },
            ).first()

        if not row or row[0] is None:
            return 0.0

        return float(row[0])

    def _calculate_distance(
        self,
        observations: list[dict[str, Any]],
    ) -> float:
        """
        Sum distances between consecutive observed cameras.

        If a direct topology edge does not exist, distance is not guessed.
        """

        distance = 0.0

        for previous, current in zip(
            observations,
            observations[1:],
        ):
            distance += self._get_transition_distance(
                int(previous["camera_id"]),
                int(current["camera_id"]),
            )

        return distance

    def _calculate_stop_count(
        self,
        observations: list[dict[str, Any]],
    ) -> int:
        """
        Count obvious stops using long gaps between consecutive
        observations.

        A gap of 5+ minutes is treated as a stop.
        """

        stop_count = 0

        for previous, current in zip(
            observations,
            observations[1:],
        ):
            gap = (
                current["ts"] - previous["ts"]
            ).total_seconds()

            if gap >= 5 * 60:
                stop_count += 1

        return stop_count

    def _get_best_plate(
        self,
        observations: list[dict[str, Any]],
    ) -> tuple[Optional[str], Optional[float]]:
        candidates = [
            observation
            for observation in observations
            if observation["plate_text"]
            and observation["plate_conf"] is not None
        ]

        if not candidates:
            return None, None

        best = max(
            candidates,
            key=lambda item: float(
                item["plate_conf"]
            ),
        )

        return (
            str(best["plate_text"]),
            float(best["plate_conf"]),
        )

    def _journey_exists(
        self,
        vehicle_id: UUID,
    ) -> bool:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id
                    FROM vehicle_journeys
                    WHERE vehicle_id = :vehicle_id
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"vehicle_id": str(vehicle_id)},
            ).first()

        return row is not None

    def _write_journey(
        self,
        vehicle_id: UUID,
        observations: list[dict[str, Any]],
    ) -> Optional[str]:

        if not observations:
            return None

        start_ts = observations[0]["ts"]
        end_ts = observations[-1]["ts"]

        duration_s = max(
            0.0,
            (end_ts - start_ts).total_seconds(),
        )

        distance_m = self._calculate_distance(
            observations
        )

        avg_speed_kmh = 0.0

        if duration_s > 0 and distance_m > 0:
            avg_speed_kmh = (
                distance_m / duration_s
            ) * 3.6

        camera_ids = {
            int(item["camera_id"])
            for item in observations
        }

        start_zone_id = observations[0]["zone_id"]
        end_zone_id = observations[-1]["zone_id"]

        stop_count = self._calculate_stop_count(
            observations
        )

        plate_best, plate_conf = self._get_best_plate(
            observations
        )

        with self.engine.begin() as conn:

            # Finalize best-known vehicle plate.
            if plate_best:
                conn.execute(
                    text(
                        """
                        UPDATE vehicles
                        SET
                            plate_best = :plate_best,
                            plate_conf = :plate_conf,
                            first_seen = :first_seen,
                            last_seen = :last_seen
                        WHERE id = :vehicle_id
                        """
                    ),
                    {
                        "vehicle_id": str(vehicle_id),
                        "plate_best": plate_best,
                        "plate_conf": plate_conf,
                        "first_seen": start_ts,
                        "last_seen": end_ts,
                    },
                )
            else:
                conn.execute(
                    text(
                        """
                        UPDATE vehicles
                        SET
                            first_seen = :first_seen,
                            last_seen = :last_seen
                        WHERE id = :vehicle_id
                        """
                    ),
                    {
                        "vehicle_id": str(vehicle_id),
                        "first_seen": start_ts,
                        "last_seen": end_ts,
                    },
                )

            # Avoid duplicate journey rows.
            existing = conn.execute(
                text(
                    """
                    SELECT id
                    FROM vehicle_journeys
                    WHERE vehicle_id = :vehicle_id
                    LIMIT 1
                    """
                ),
                {
                    "vehicle_id": str(vehicle_id)
                },
            ).first()

            if existing:
                return str(existing[0])

            row = conn.execute(
                text(
                    """
                    INSERT INTO vehicle_journeys
                    (
                        vehicle_id,
                        start_ts,
                        end_ts,
                        start_zone_id,
                        end_zone_id,
                        distance_est_m,
                        duration_s,
                        avg_speed_kmh,
                        stop_count,
                        camera_count,
                        anomaly_score,
                        congestion_exposure
                    )
                    VALUES
                    (
                        :vehicle_id,
                        :start_ts,
                        :end_ts,
                        :start_zone_id,
                        :end_zone_id,
                        :distance_est_m,
                        :duration_s,
                        :avg_speed_kmh,
                        :stop_count,
                        :camera_count,
                        NULL,
                        NULL
                    )
                    RETURNING id
                    """
                ),
                {
                    "vehicle_id": str(vehicle_id),
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "start_zone_id": start_zone_id,
                    "end_zone_id": end_zone_id,
                    "distance_est_m": distance_m,
                    "duration_s": duration_s,
                    "avg_speed_kmh": avg_speed_kmh,
                    "stop_count": stop_count,
                    "camera_count": len(camera_ids),
                },
            ).first()

        return str(row[0]) if row else None

    def close_finished_journeys(self) -> list[dict[str, Any]]:
        """
        Aggregate every vehicle that has been idle long enough.
        """

        results: list[dict[str, Any]] = []

        for vehicle in self._get_finished_vehicles():

            vehicle_id = vehicle["vehicle_id"]

            observations = self._get_observations(
                vehicle_id
            )

            if not observations:
                continue

            journey_id = self._write_journey(
                vehicle_id,
                observations,
            )

            results.append(
                {
                    "vehicle_id": str(vehicle_id),
                    "journey_id": journey_id,
                    "camera_count": len(
                        {
                            item["camera_id"]
                            for item in observations
                        }
                    ),
                    "start_ts": observations[0]["ts"],
                    "end_ts": observations[-1]["ts"],
                }
            )

        return results

    def close(self) -> None:
        self.engine.dispose()


def run_journey_aggregation() -> list[dict[str, Any]]:
    aggregator = VehicleJourneyAggregator()

    try:
        return aggregator.close_finished_journeys()
    finally:
        aggregator.close()


__all__ = [
    "VehicleJourneyAggregator",
    "run_journey_aggregation",
]