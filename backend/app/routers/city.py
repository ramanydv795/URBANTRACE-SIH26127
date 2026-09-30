from fastapi import APIRouter

from app.config import get_demo_city

router = APIRouter(prefix="/api/city", tags=["city"])


@router.get("/summary")
async def city_summary():
    city = get_demo_city()
    return {
        "city_name": city.get("city_name"),
        "zones": len(city.get("zones", [])),
        "roads": len(city.get("roads", [])),
        "intersections": len(city.get("intersections", [])),
        "cameras": len(city.get("cameras", [])),
        "topology_edges": len(city.get("camera_topology", [])),
    }


@router.get("/zones")
async def zones():
    return get_demo_city().get("zones", [])


@router.get("/roads")
async def roads():
    return get_demo_city().get("roads", [])


@router.get("/intersections")
async def intersections():
    return get_demo_city().get("intersections", [])


@router.get("/topology")
async def topology():
    return get_demo_city().get("camera_topology", [])
