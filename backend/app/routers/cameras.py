from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.config import get_demo_city
from app.db import SessionLocal

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


async def get_camera_statuses():
    async with SessionLocal() as session:
        result = await session.execute(
            text("SELECT code, status FROM cameras ORDER BY code")
        )
        return {row.code: row.status for row in result}


@router.get("")
async def list_cameras():
    """Returns configured demo-city cameras with persisted database status."""
    city = get_demo_city()
    status_map = await get_camera_statuses()

    cameras = [
        {
            "code": c["code"],
            "name": c["name"],
            "lat": c["lat"],
            "lng": c["lng"],
            "road": c["road"],
            "zone": c["zone"],
            "direction_deg": c["direction_deg"],
            "status": status_map.get(c["code"], "offline"),
        }
        for c in city.get("cameras", [])
    ]

    return {"count": len(cameras), "cameras": cameras}


@router.get("/{code}")
async def get_camera(code: str):
    city = get_demo_city()

    camera = next(
        (
            c for c in city.get("cameras", [])
            if c["code"].lower() == code.lower()
        ),
        None,
    )

    if not camera:
        raise HTTPException(
            status_code=404,
            detail=f"Camera '{code}' not found in demo city config",
        )

    status_map = await get_camera_statuses()

    return {
        **camera,
        "status": status_map.get(camera["code"], "offline"),
    }


@router.get("/{code}/health")
async def camera_health(code: str):
    city = get_demo_city()

    camera = next(
        (
            c for c in city.get("cameras", [])
            if c["code"].lower() == code.lower()
        ),
        None,
    )

    if not camera:
        raise HTTPException(
            status_code=404,
            detail=f"Camera '{code}' not found",
        )

    status_map = await get_camera_statuses()

    return {
        "camera": code,
        "status": status_map.get(camera["code"], "offline"),
        "fps": None,
        "processing_latency_ms": None,
        "detection_count": None,
        "ocr_success_rate": None,
        "last_heartbeat": None,
        "note": "Camera status is read from the persisted camera registry.",
    }
