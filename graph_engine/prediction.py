"""
URBANTRACE Part 4.2 - Next-Camera Prediction

Predicts the most likely next camera for a vehicle.

Learning:
1. Observed auto-linked transitions from camera_transitions.
2. camera_topology.historical_freq as prior.
3. Cold start: uniform probability across reachable neighbors
   when both sources have zero information.

Read-only module. No database writes.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import create_engine, text

from app.config import get_settings


class NextCameraPredictor:
    def __init__(self) -> None:
        settings = get_settings()

        self.engine = create_engine(
            settings.sync_database_url,
            pool_pre_ping=True,
        )

    def _get_camera_id(self, camera_code: str) -> Optional[int]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id
                    FROM cameras
                    WHERE code = :code
                    LIMIT 1
                    """
                ),
                {"code": camera_code},
            ).first()

        return int(row[0]) if row else None

    def _get_camera_code(self, camera_id: int) -> Optional[str]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT code
                    FROM cameras
                    WHERE id = :camera_id
                    LIMIT 1
                    """
                ),
                {"camera_id": camera_id},
            ).first()

        return str(row[0]) if row else None

    def _get_reachable_neighbors(
        self,
        camera_id: int,
    ) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        ct.to_camera_id AS camera_id,
                        c.code AS camera_code,
                        ct.historical_freq
                    FROM camera_topology ct
                    JOIN cameras c
                        ON c.id = ct.to_camera_id
                    WHERE ct.from_camera_id = :camera_id
                    ORDER BY ct.to_camera_id
                    """
                ),
                {"camera_id": camera_id},
            ).mappings().all()

        return [dict(row) for row in rows]

    def _get_observed_counts(
        self,
        camera_id: int,
    ) -> dict[int, int]:
        """
        Count actual auto-linked transitions from this camera.
        """

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        vo_from.camera_id AS from_camera_id,
                        vo_to.camera_id AS to_camera_id,
                        COUNT(*) AS transition_count
                    FROM camera_transitions ct
                    JOIN vehicle_observations vo_from
                        ON vo_from.id = ct.from_observation_id
                    JOIN vehicle_observations vo_to
                        ON vo_to.id = ct.to_observation_id
                    WHERE vo_from.camera_id = :camera_id
                      AND ct.status = 'auto_linked'
                    GROUP BY
                        vo_from.camera_id,
                        vo_to.camera_id
                    """
                ),
                {"camera_id": camera_id},
            ).mappings().all()

        return {
            int(row["to_camera_id"]): int(
                row["transition_count"]
            )
            for row in rows
        }

    def predict(
        self,
        camera_code: str,
    ) -> list[dict[str, Any]]:
        """
        Return ranked next-camera predictions.

        Each result contains:
        - camera
        - probability
        - observed transition count
        - topology historical frequency
        """

        camera_id = self._get_camera_id(camera_code)

        if camera_id is None:
            return []

        neighbors = self._get_reachable_neighbors(
            camera_id
        )

        if not neighbors:
            return []

        observed = self._get_observed_counts(
            camera_id
        )

        # -------------------------------------------------------------
        # Determine prediction weights
        # -------------------------------------------------------------

        scores: list[dict[str, Any]] = []

        has_observed_data = any(
            observed.get(
                int(item["camera_id"]),
                0,
            ) > 0
            for item in neighbors
        )

        has_historical_data = any(
            int(item["historical_freq"] or 0) > 0
            for item in neighbors
        )

        for item in neighbors:
            target_id = int(
                item["camera_id"]
            )

            observed_count = observed.get(
                target_id,
                0,
            )

            historical_count = int(
                item["historical_freq"] or 0
            )

            # ---------------------------------------------------------
            # Case 1: observed transition data exists.
            # Give real observations priority.
            # ---------------------------------------------------------

            if has_observed_data:
                score = float(observed_count)

                # Blend topology prior only when it exists.
                if has_historical_data:
                    score = (
                        0.8 * score
                        + 0.2 * historical_count
                    )

            # ---------------------------------------------------------
            # Case 2: no observed data but topology history exists.
            # ---------------------------------------------------------

            elif has_historical_data:
                score = float(historical_count)

            # ---------------------------------------------------------
            # Case 3: complete cold start.
            # Uniform distribution.
            # ---------------------------------------------------------

            else:
                score = 1.0

            scores.append(
                {
                    "camera_id": target_id,
                    "camera": item["camera_code"],
                    "raw_score": score,
                    "observed_transition_count": (
                        observed_count
                    ),
                    "historical_freq": (
                        historical_count
                    ),
                }
            )

        total = sum(
            item["raw_score"]
            for item in scores
        )

        if total <= 0:
            total = float(len(scores))

            for item in scores:
                item["raw_score"] = 1.0

        for item in scores:
            item["probability"] = round(
                item["raw_score"] / total,
                6,
            )
            del item["raw_score"]

        scores.sort(
            key=lambda item: item["probability"],
            reverse=True,
        )

        return scores

    def predict_from_camera_id(
        self,
        camera_id: int,
    ) -> list[dict[str, Any]]:
        camera_code = self._get_camera_code(
            camera_id
        )

        if camera_code is None:
            return []

        return self.predict(camera_code)

    def close(self) -> None:
        self.engine.dispose()


def predict_next_camera(
    camera_code: str,
) -> list[dict[str, Any]]:
    predictor = NextCameraPredictor()

    try:
        return predictor.predict(camera_code)
    finally:
        predictor.close()


__all__ = [
    "NextCameraPredictor",
    "predict_next_camera",
]