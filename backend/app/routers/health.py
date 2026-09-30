from fastapi import APIRouter
import redis.asyncio as redis

from app.config import get_demo_city, get_settings
from app.db import check_database_connection

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    """Liveness check. Always returns 200 if the process is up."""
    return {"status": "ok", "service": "urbantrace-api"}


@router.get("/health/detailed")
async def health_detailed():
    """Readiness check: verifies DB, Redis, and demo city config are all
    reachable/loadable. Used by ops to confirm the stack is actually usable,
    not just that the process started."""
    settings = get_settings()

    db_ok = await check_database_connection()

    redis_ok = False
    try:
        client = redis.Redis(host=settings.redis_host, port=settings.redis_port, socket_timeout=2)
        redis_ok = await client.ping()
        await client.aclose()
    except Exception:
        redis_ok = False

    demo_city_ok = True
    demo_city_summary = {}
    try:
        city = get_demo_city()
        demo_city_summary = {
            "cameras": len(city.get("cameras", [])),
            "roads": len(city.get("roads", [])),
            "zones": len(city.get("zones", [])),
            "topology_edges": len(city.get("camera_topology", [])),
        }
    except Exception as e:
        demo_city_ok = False
        demo_city_summary = {"error": str(e)}

    overall = "ok" if (db_ok and redis_ok and demo_city_ok) else "degraded"

    return {
        "status": overall,
        "checks": {
            "database": "ok" if db_ok else "unreachable",
            "redis": "ok" if redis_ok else "unreachable",
            "demo_city_config": "ok" if demo_city_ok else "error",
        },
        "demo_city": demo_city_summary,
    }
