from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import create_engine, text

from app.config import get_settings

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])

settings = get_settings()
engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
)


@router.get("/search")
def search_vehicles(
    plate: Optional[str] = Query(None),
    vehicle_type: Optional[str] = Query(None, alias="type"),
    color: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
):
    conditions = []
    params = {}

    if plate:
        conditions.append(
            "LOWER(v.plate_best) LIKE LOWER(:plate)"
        )
        params["plate"] = f"%{plate}%"

    if vehicle_type:
        conditions.append(
            "LOWER(v.vehicle_type) = LOWER(:vehicle_type)"
        )
        params["vehicle_type"] = vehicle_type

    if color:
        conditions.append(
            "LOWER(v.color) = LOWER(:color)"
        )
        params["color"] = color

    where = ""

    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    params["limit"] = limit

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT
                    v.id,
                    v.plate_best,
                    v.plate_conf,
                    v.vehicle_type,
                    v.color,
                    v.first_seen,
                    v.last_seen
                FROM vehicles v
                {where}
                ORDER BY v.last_seen DESC NULLS LAST
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()

    return {
        "count": len(rows),
        "items": [dict(row) for row in rows],
    }


@router.get("/{vehicle_id}/journey")
def get_vehicle_journey(vehicle_id: UUID):

    with engine.connect() as conn:

        vehicle = conn.execute(
            text(
                """
                SELECT
                    id,
                    plate_best,
                    plate_conf,
                    vehicle_type,
                    color,
                    first_seen,
                    last_seen
                FROM vehicles
                WHERE id = :vehicle_id
                """
            ),
            {"vehicle_id": str(vehicle_id)},
        ).mappings().first()

        if not vehicle:
            raise HTTPException(
                status_code=404,
                detail="Vehicle not found",
            )

        observations = conn.execute(
            text(
                """
                SELECT
                    vo.id AS observation_id,
                    vo.ts,
                    vo.camera_id,
                    c.code AS camera,
                    c.zone_id,
                    vo.plate_text,
                    vo.plate_conf,
                    vo.vehicle_type,
                    vo.color
                FROM vehicle_observations vo
                JOIN cameras c
                    ON c.id = vo.camera_id
                WHERE vo.vehicle_id = :vehicle_id
                ORDER BY vo.ts ASC
                """
            ),
            {"vehicle_id": str(vehicle_id)},
        ).mappings().all()

        transitions = conn.execute(
            text(
                """
                SELECT
                    ct.id,
                    ct.from_observation_id,
                    ct.to_observation_id,
                    ct.travel_time_s,
                    ct.est_speed_kmh,
                    ct.confidence,
                    ct.status,
                    ct.evidence
                FROM camera_transitions ct
                WHERE ct.vehicle_id = :vehicle_id
                ORDER BY ct.created_at ASC
                """
            ),
            {"vehicle_id": str(vehicle_id)},
        ).mappings().all()

        segments = conn.execute(
            text(
                """
                SELECT
                    id,
                    from_camera_id,
                    to_camera_id,
                    segment_type,
                    path_camera_ids,
                    confidence,
                    created_at
                FROM trajectory_segments
                WHERE vehicle_id = :vehicle_id
                ORDER BY created_at ASC
                """
            ),
            {"vehicle_id": str(vehicle_id)},
        ).mappings().all()

        journey = conn.execute(
            text(
                """
                SELECT
                    id,
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
                FROM vehicle_journeys
                WHERE vehicle_id = :vehicle_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"vehicle_id": str(vehicle_id)},
        ).mappings().first()

    return {
        "vehicle": dict(vehicle),
        "observations": [dict(row) for row in observations],
        "transitions": [dict(row) for row in transitions],
        "trajectory_segments": [dict(row) for row in segments],
        "journey": dict(journey) if journey else None,
    }


@router.get("/{vehicle_id}/next-camera")
def get_next_camera(vehicle_id: UUID):

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    c.code AS camera
                FROM vehicle_observations vo
                JOIN cameras c
                    ON c.id = vo.camera_id
                WHERE vo.vehicle_id = :vehicle_id
                ORDER BY vo.ts DESC
                LIMIT 1
                """
            ),
            {"vehicle_id": str(vehicle_id)},
        ).first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Vehicle has no observations",
        )

    from graph_engine.prediction import (
        predict_next_camera,
    )

    predictions = predict_next_camera(
        str(row[0])
    )

    return {
        "vehicle_id": str(vehicle_id),
        "current_camera": str(row[0]),
        "predictions": predictions,
    }
