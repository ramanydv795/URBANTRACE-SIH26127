from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.config import get_settings
from sqlalchemy import create_engine


router = APIRouter(
    prefix="/api/transitions",
    tags=["transitions"],
)

settings = get_settings()
engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
)


@router.get("")
def list_transitions(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    """
    List camera transitions with optional status filtering.
    """

    query = """
       SELECT
    ct.id,
    ct.vehicle_id,
    ct.from_observation_id,
    ct.to_observation_id,
    ct.travel_time_s,
    ct.est_speed_kmh,
    ct.direction_ok,
    ct.topology_ok,
    ct.time_feasible,
    ct.plate_similarity,
    ct.reid_similarity,
    ct.confidence,
    ct.status,
    ct.evidence,
    ct.created_at,

    cf.code AS from_camera,
    ca.code AS to_camera

FROM camera_transitions ct

JOIN vehicle_observations vof
    ON vof.id = ct.from_observation_id

JOIN vehicle_observations vot
    ON vot.id = ct.to_observation_id

JOIN cameras cf
    ON cf.id = vof.camera_id

JOIN cameras ca
    ON ca.id = vot.camera_id
    """

    params = {"limit": limit}

    if status:
        query += " WHERE ct.status = :status"
        params["status"] = status

    query += """
        ORDER BY ct.created_at DESC
        LIMIT :limit
    """

    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()

    return {
        "count": len(rows),
        "items": [dict(row) for row in rows],
    }


@router.get("/{transition_id}/explain")
def explain_transition(transition_id: UUID):
    """
    Return the complete evidence used to explain one transition.
    """

    query = """
        SELECT
            ct.id,
            ct.vehicle_id,
            ct.from_observation_id,
            ct.to_observation_id,
            ct.travel_time_s,
            ct.est_speed_kmh,
            ct.direction_ok,
            ct.topology_ok,
            ct.time_feasible,
            ct.plate_similarity,
            ct.reid_similarity,
            ct.confidence,
            ct.status,
            ct.evidence,
            ct.created_at,

            cf.code AS from_camera,
            ca.code AS to_camera,

            vof.ts AS from_ts,
            vot.ts AS to_ts,
            vof.plate_text AS from_plate,
            vot.plate_text AS to_plate

        FROM camera_transitions ct

        JOIN vehicle_observations vof
            ON vof.id = ct.from_observation_id

        JOIN vehicle_observations vot
            ON vot.id = ct.to_observation_id

        JOIN cameras cf
            ON cf.id = vof.camera_id

        JOIN cameras ca
            ON ca.id = vot.camera_id

        WHERE ct.id = :transition_id
    """

    with engine.connect() as conn:
        row = conn.execute(
            text(query),
            {"transition_id": str(transition_id)},
        ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Transition not found",
        )

    return dict(row)


@router.get("/vehicle/{vehicle_id}/journey")
def vehicle_journey(vehicle_id: UUID):
    """
    Return the chronological auto-linked journey of a vehicle.
    """

    query = """
        SELECT
            ct.id AS transition_id,
            ct.from_observation_id,
            ct.to_observation_id,
            ct.travel_time_s,
            ct.est_speed_kmh,
            ct.plate_similarity,
            ct.reid_similarity,
            ct.confidence,
            ct.status,

            cf.code AS from_camera,
            ca.code AS to_camera,

            vof.ts AS from_ts,
            vot.ts AS to_ts

        FROM camera_transitions ct

        JOIN vehicle_observations vof
            ON vof.id = ct.from_observation_id

        JOIN vehicle_observations vot
            ON vot.id = ct.to_observation_id

        JOIN cameras cf
            ON cf.id = vof.camera_id

        JOIN cameras ca
            ON ca.id = vot.camera_id

        WHERE ct.vehicle_id = :vehicle_id
          AND ct.status = 'auto_linked'

        ORDER BY vof.ts ASC
    """

    with engine.connect() as conn:
        rows = conn.execute(
            text(query),
            {"vehicle_id": str(vehicle_id)},
        ).mappings().all()

    return {
        "vehicle_id": str(vehicle_id),
        "hop_count": len(rows),
        "journey": [dict(row) for row in rows],
    }