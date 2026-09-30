from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text


# Make backend/app importable
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings


class GraphRepository:
    """
    PostgreSQL repository for URBANTRACE Part 3.

    Handles:
    - unresolved observations
    - Re-ID embeddings
    - camera topology
    - vehicles
    - camera transitions
    - review queue
    """

    def __init__(self) -> None:
        settings = get_settings()

        self.engine = create_engine(
            settings.sync_database_url,
            pool_pre_ping=True,
        )

    # ------------------------------------------------------------------
    # OBSERVATIONS
    # ------------------------------------------------------------------

    def get_unresolved_observations(self) -> list[dict[str, Any]]:
        """
        Return unresolved vehicle observations ordered oldest first.

        Important:
        vehicle_observations stores camera_id, not camera_code.
        """

        sql = text(
            """
            SELECT
                vo.id,
                vo.camera_id,
                c.code AS camera_code,
                vo.vehicle_id,
                vo.ts,
                vo.track_id,
                vo.bbox,
                vo.frame_ref,
                vo.plate_text,
                vo.plate_conf,
                vo.vehicle_type,
                vo.type_conf,
                vo.color,
                vo.color_conf,
                vo.detection_conf
            FROM vehicle_observations vo
            JOIN cameras c
                ON c.id = vo.camera_id
            WHERE vo.vehicle_id IS NULL
            ORDER BY vo.ts ASC
            """
        )

        with self.engine.connect() as conn:
            rows = conn.execute(sql).mappings().all()

        return [dict(row) for row in rows]

    def get_observation(self, observation_id: str) -> dict[str, Any] | None:
        sql = text(
            """
            SELECT
                vo.id,
                vo.camera_id,
                c.code AS camera_code,
                vo.vehicle_id,
                vo.ts,
                vo.track_id,
                vo.bbox,
                vo.frame_ref,
                vo.plate_text,
                vo.plate_conf,
                vo.vehicle_type,
                vo.type_conf,
                vo.color,
                vo.color_conf,
                vo.detection_conf
            FROM vehicle_observations vo
            JOIN cameras c
                ON c.id = vo.camera_id
            WHERE vo.id = CAST(:observation_id AS uuid)
            """
        )

        with self.engine.connect() as conn:
            row = conn.execute(
                sql,
                {"observation_id": observation_id},
            ).mappings().first()

        return dict(row) if row else None

    def get_reid_vector(self, observation_id: str) -> list[float] | None:
        sql = text(
            """
            SELECT vector
            FROM reid_embeddings
            WHERE observation_id = CAST(:observation_id AS uuid)
            ORDER BY created_at DESC
            LIMIT 1
            """
        )

        with self.engine.connect() as conn:
            row = conn.execute(
                sql,
                {"observation_id": observation_id},
            ).first()

        if not row:
            return None

        vector = row[0]

        if vector is None:
            return None

        if isinstance(vector, list):
            return [float(x) for x in vector]

        if isinstance(vector, str):
            cleaned = vector.strip()

            if cleaned.startswith("[") and cleaned.endswith("]"):
                cleaned = cleaned[1:-1]

            if not cleaned:
                return []

            return [
                float(x.strip())
                for x in cleaned.split(",")
                if x.strip()
            ]

        try:
            return [float(x) for x in vector]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # CAMERA / TOPOLOGY
    # ------------------------------------------------------------------

    def get_camera_id(self, camera_code: str) -> int | None:
        sql = text(
            """
            SELECT id
            FROM cameras
            WHERE code = :camera_code
            LIMIT 1
            """
        )

        with self.engine.connect() as conn:
            row = conn.execute(
                sql,
                {"camera_code": camera_code},
            ).first()

        return int(row[0]) if row else None

    def get_topology_edge(
        self,
        from_camera_code: str,
        to_camera_code: str,
    ) -> dict[str, Any] | None:

        sql = text(
            """
            SELECT
                ct.id,
                ct.from_camera_id,
                ct.to_camera_id,
                ct.distance_m,
                ct.min_travel_s,
                ct.max_travel_s,
                ct.typical_travel_s,
                ct.historical_freq
            FROM camera_topology ct
            JOIN cameras cf
                ON cf.id = ct.from_camera_id
            JOIN cameras ctg
                ON ctg.id = ct.to_camera_id
            WHERE cf.code = :from_camera_code
              AND ctg.code = :to_camera_code
            LIMIT 1
            """
        )

        with self.engine.connect() as conn:
            row = conn.execute(
                sql,
                {
                    "from_camera_code": from_camera_code,
                    "to_camera_code": to_camera_code,
                },
            ).mappings().first()

        return dict(row) if row else None

    def get_outgoing_topology(
        self,
        camera_code: str,
    ) -> list[dict[str, Any]]:

        sql = text(
            """
            SELECT
                ct.id,
                cf.code AS from_camera_code,
                ctg.code AS to_camera_code,
                ct.distance_m,
                ct.min_travel_s,
                ct.max_travel_s,
                ct.typical_travel_s,
                ct.historical_freq
            FROM camera_topology ct
            JOIN cameras cf
                ON cf.id = ct.from_camera_id
            JOIN cameras ctg
                ON ctg.id = ct.to_camera_id
            WHERE cf.code = :camera_code
            ORDER BY ct.id
            """
        )

        with self.engine.connect() as conn:
            rows = conn.execute(
                sql,
                {"camera_code": camera_code},
            ).mappings().all()

        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # VEHICLES
    # ------------------------------------------------------------------

    def create_vehicle(
        self,
        observation: dict[str, Any],
    ) -> str:

        sql = text(
            """
            INSERT INTO vehicles
            (
                plate_best,
                plate_conf,
                vehicle_type,
                color,
                first_seen,
                last_seen
            )
            VALUES
            (
                :plate_best,
                :plate_conf,
                :vehicle_type,
                :color,
                :first_seen,
                :last_seen
            )
            RETURNING id
            """
        )

        with self.engine.begin() as conn:
            row = conn.execute(
                sql,
                {
                    "plate_best": observation.get("plate_text"),
                    "plate_conf": observation.get("plate_conf"),
                    "vehicle_type": observation.get("vehicle_type"),
                    "color": observation.get("color"),
                    "first_seen": observation.get("ts"),
                    "last_seen": observation.get("ts"),
                },
            ).first()

        return str(row[0])

    def update_vehicle_times(
        self,
        vehicle_id: str,
        first_seen: Any | None = None,
        last_seen: Any | None = None,
    ) -> None:

        sql = text(
            """
            UPDATE vehicles
            SET
                first_seen = COALESCE(:first_seen, first_seen),
                last_seen = COALESCE(:last_seen, last_seen)
            WHERE id = CAST(:vehicle_id AS uuid)
            """
        )

        with self.engine.begin() as conn:
            conn.execute(
                sql,
                {
                    "vehicle_id": vehicle_id,
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                },
            )

    def assign_vehicle(
        self,
        observation_id: str,
        vehicle_id: str,
    ) -> None:

        sql = text(
            """
            UPDATE vehicle_observations
            SET vehicle_id = CAST(:vehicle_id AS uuid)
            WHERE id = CAST(:observation_id AS uuid)
            """
        )

        with self.engine.begin() as conn:
            conn.execute(
                sql,
                {
                    "observation_id": observation_id,
                    "vehicle_id": vehicle_id,
                },
            )

    # ------------------------------------------------------------------
    # TRANSITIONS
    # ------------------------------------------------------------------

    def create_transition(
        self,
        from_observation_id: str,
        to_observation_id: str,
        vehicle_id: str | None,
        fusion_result: Any,
        status: str,
    ) -> str:

        evidence = getattr(
            fusion_result,
            "evidence",
            {},
        )

        raw_signals = getattr(
            fusion_result,
            "raw_signals",
            {},
        )

        score = float(
            getattr(
                fusion_result,
                "score",
                0.0,
            )
        )

        time_details = getattr(
            fusion_result,
            "time_details",
            {},
        )

        travel_time_s = time_details.get(
            "travel_time_s"
        )

        topology_ok = bool(
            raw_signals.get("topology", 0.0) > 0
        )

        direction_ok = bool(
            raw_signals.get("direction", 0.0) > 0
        )

        time_feasible = bool(
            raw_signals.get("time", 0.0) > 0
        )

        plate_similarity = raw_signals.get(
            "plate"
        )

        reid_similarity = raw_signals.get(
            "reid"
        )

        est_speed_kmh = None

        distance_m = time_details.get(
            "distance_m"
        )

        if (
            distance_m is not None
            and travel_time_s is not None
            and float(travel_time_s) > 0
        ):
            est_speed_kmh = (
                float(distance_m)
                / float(travel_time_s)
                * 3.6
            )

        sql = text(
            """
            INSERT INTO camera_transitions
            (
                vehicle_id,
                from_observation_id,
                to_observation_id,
                travel_time_s,
                est_speed_kmh,
                direction_ok,
                topology_ok,
                time_feasible,
                plate_similarity,
                reid_similarity,
                confidence,
                status,
                evidence
            )
            VALUES
            (
                CAST(:vehicle_id AS uuid),
                CAST(:from_observation_id AS uuid),
                CAST(:to_observation_id AS uuid),
                :travel_time_s,
                :est_speed_kmh,
                :direction_ok,
                :topology_ok,
                :time_feasible,
                :plate_similarity,
                :reid_similarity,
                :confidence,
                :status,
                CAST(:evidence AS jsonb)
            )
            RETURNING id
            """
        )

        import json

        evidence_payload = dict(evidence)

        evidence_payload.update(
            {
                "raw_signals": raw_signals,
                "time_details": time_details,
                "fusion_score": score,
            }
        )

        with self.engine.begin() as conn:
            row = conn.execute(
                sql,
                {
                    "vehicle_id": vehicle_id,
                    "from_observation_id": from_observation_id,
                    "to_observation_id": to_observation_id,
                    "travel_time_s": travel_time_s,
                    "est_speed_kmh": est_speed_kmh,
                    "direction_ok": direction_ok,
                    "topology_ok": topology_ok,
                    "time_feasible": time_feasible,
                    "plate_similarity": plate_similarity,
                    "reid_similarity": reid_similarity,
                    "confidence": score,
                    "status": status,
                    "evidence": json.dumps(
                        evidence_payload,
                        default=str,
                    ),
                },
            ).first()

        return str(row[0])

    def create_review_queue_item(
        self,
        transition_id: str,
    ) -> str:

        sql = text(
            """
            INSERT INTO review_queue
            (
                camera_transition_id,
                status
            )
            VALUES
            (
                CAST(:transition_id AS uuid),
                'pending'
            )
            RETURNING id
            """
        )

        with self.engine.begin() as conn:
            row = conn.execute(
                sql,
                {"transition_id": transition_id},
            ).first()

        return str(row[0])

    # ------------------------------------------------------------------
    # CLEANUP
    # ------------------------------------------------------------------

    def close(self) -> None:
        self.engine.dispose()