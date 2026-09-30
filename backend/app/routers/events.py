from fastapi import APIRouter, Query
from sqlalchemy import create_engine, text

from app.config import get_settings


engine = create_engine(
    get_settings().sync_database_url,
    pool_pre_ping=True,
)

router = APIRouter(
    prefix="/api/events",
    tags=["traffic events"],
)


@router.get("")
def get_events(
    event_type: str | None = Query(default=None),
    simulated: bool | None = Query(default=None),
):
    query = """
        SELECT
            id,
            type,
            start_ts,
            end_ts,
            affected_road_ids,
            is_simulated,
            created_at
        FROM traffic_events
        WHERE 1 = 1
    """

    params = {}

    if event_type:
        query += " AND type = :event_type"
        params["event_type"] = event_type

    if simulated is not None:
        query += " AND is_simulated = :simulated"
        params["simulated"] = simulated

    query += " ORDER BY start_ts DESC"

    with engine.connect() as conn:
        rows = conn.execute(
            text(query),
            params,
        ).mappings().all()

    return {
        "count": len(rows),
        "items": [dict(row) for row in rows],
    }