"""
Persistence layer for the Part 2 perception pipeline.

Writes:
    vehicle_observations
    reid_embeddings
    camera_health_metrics

Part 2 intentionally does NOT create global vehicle identities.
vehicle_id remains NULL until Part 3 cross-camera fusion.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text


logger = logging.getLogger("vision.db")


# -------------------------------------------------------------------
# Make backend/app importable when running from project root
# -------------------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.config import get_settings
from vision.contracts import VehicleObservationResult


class PerceptionDBWriter:

    def __init__(self):
        settings = get_settings()

        self.engine = create_engine(
            settings.sync_database_url,
            pool_pre_ping=True,
        )

    # ----------------------------------------------------------------
    # Camera
    # ----------------------------------------------------------------

    def get_camera_id(
        self,
        camera_code: str,
    ) -> int:

        with self.engine.connect() as conn:

            row = conn.execute(
                text(
                    """
                    SELECT id
                    FROM cameras
                    WHERE code = :code
                    """
                ),
                {
                    "code": camera_code,
                },
            ).first()

        if row is None:
            raise ValueError(
                f"Camera '{camera_code}' does not exist "
                "in PostgreSQL. Run the city seed first."
            )

        return int(row.id)

    # ----------------------------------------------------------------
    # Camera status
    # ----------------------------------------------------------------

    def set_camera_status(
        self,
        camera_code: str,
        status: str,
    ) -> None:

        with self.engine.begin() as conn:

            conn.execute(
                text(
                    """
                    UPDATE cameras
                    SET status = :status
                    WHERE code = :code
                    """
                ),
                {
                    "status": status,
                    "code": camera_code,
                },
            )

    # ----------------------------------------------------------------
    # Vehicle observation + Re-ID embedding
    # ----------------------------------------------------------------

    def write_observation(
        self,
        result: VehicleObservationResult,
        camera_id: int,
    ) -> str:

        with self.engine.begin() as conn:

            row = conn.execute(
                text(
                    """
                    INSERT INTO vehicle_observations
                    (
                        camera_id,
                        vehicle_id,
                        ts,
                        track_id,
                        bbox,
                        frame_ref,
                        plate_text,
                        plate_conf,
                        vehicle_type,
                        type_conf,
                        color,
                        color_conf,
                        detection_conf
                    )
                    VALUES
                    (
                        :camera_id,
                        NULL,
                        :ts,
                        :track_id,
                        CAST(:bbox AS jsonb),
                        :frame_ref,
                        :plate_text,
                        :plate_conf,
                        :vehicle_type,
                        :type_conf,
                        :color,
                        :color_conf,
                        :detection_conf
                    )
                    RETURNING id
                    """
                ),
                {
                    "camera_id": camera_id,
                    "ts": result.ts,
                    "track_id": result.track_id,
                    "bbox": json.dumps(
                        result.bbox.as_dict()
                    ),
                    "frame_ref": result.frame_ref,
                    "plate_text": result.plate_text,
                    "plate_conf": result.plate_conf,
                    "vehicle_type": result.vehicle_type,
                    "type_conf": result.type_conf,
                    "color": result.color,
                    "color_conf": result.color_conf,
                    "detection_conf": result.detection_conf,
                },
            ).first()

            if row is None:
                raise RuntimeError(
                    "Failed to insert vehicle observation."
                )

            observation_id = str(row.id)

            # Re-ID embedding.
            # Global vehicle identity is intentionally NOT assigned here.
            if result.reid_vector:

                conn.execute(
                    text(
                        """
                        INSERT INTO reid_embeddings
                        (
                            observation_id,
                            model_version,
                            vector
                        )
                        VALUES
                        (
                            CAST(:observation_id AS uuid),
                            :model_version,
                            :vector
                        )
                        """
                    ),
                    {
                        "observation_id": observation_id,
                        "model_version": (
                            result.reid_model_version
                            or "unknown"
                        ),
                        "vector": result.reid_vector,
                    },
                )

        return observation_id

    # ----------------------------------------------------------------
    # Camera health metric
    # ----------------------------------------------------------------

    def write_health_metric(
        self,
        camera_id: int,
        camera_code: str,
        fps: float,
        processing_latency_ms: float,
        detection_count: int,
        ocr_success_rate: float,
        stream_health: str,
    ) -> None:

        timestamp = datetime.now(timezone.utc)

        with self.engine.begin() as conn:

            conn.execute(
                text(
                    """
                    INSERT INTO camera_health_metrics
                    (
                        camera_id,
                        ts,
                        fps,
                        processing_latency_ms,
                        detection_count,
                        ocr_success_rate,
                        stream_health
                    )
                    VALUES
                    (
                        :camera_id,
                        :ts,
                        :fps,
                        :latency,
                        :detection_count,
                        :ocr_rate,
                        :health
                    )
                    """
                ),
                {
                    "camera_id": camera_id,
                    "ts": timestamp,
                    "fps": fps,
                    "latency": processing_latency_ms,
                    "detection_count": detection_count,
                    "ocr_rate": ocr_success_rate,
                    "health": stream_health,
                },
            )

    # ----------------------------------------------------------------
    # Close database engine
    # ----------------------------------------------------------------

    def close(self) -> None:
        self.engine.dispose()