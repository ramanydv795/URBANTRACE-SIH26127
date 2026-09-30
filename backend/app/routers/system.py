import time

from fastapi import APIRouter

router = APIRouter(prefix="/api/system", tags=["system"])

_START_TIME = time.time()


@router.get("/metrics")
async def system_metrics():
    """Real process-level metrics only. Pipeline metrics (FPS, inference
    latency, queue size, vehicles tracked, events processed) are added in
    Part 2+ as those subsystems come online — they are omitted here rather
    than faked."""
    return {
        "uptime_s": round(time.time() - _START_TIME, 1),
        "active_streams": 0,
        "vehicles_tracked": 0,
        "events_processed": 0,
        "note": "Perception/graph/analytics subsystems not yet implemented (Part 2+).",
    }
