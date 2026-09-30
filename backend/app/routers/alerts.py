from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import create_engine, text

from app.config import get_settings
from graph_engine.alerts import generate_alerts

router = APIRouter(
    prefix="/api/alerts",
    tags=["alerts"],
)

settings = get_settings()

engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
)


@router.get("")
def list_alerts(
    status: Optional[str] = Query(default="open"),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Return persisted alerts generated from real intelligence."""

    generated = generate_alerts()

    query = """
        SELECT
            id,
            category,
            ref_table,
            ref_id,
            message,
            severity,
            status,
            created_at
        FROM alerts
        WHERE 1 = 1
    """

    params = {"limit": limit}

    if status:
        query += " AND status = :status"
        params["status"] = status

    if severity:
        query += " AND severity = :severity"
        params["severity"] = severity

    query += """
        ORDER BY created_at DESC
        LIMIT :limit
    """

    with engine.connect() as conn:
        rows = conn.execute(
            text(query),
            params,
        ).mappings().all()

    return {
        "count": len(rows),
        "generated": len(generated),
        "items": [dict(row) for row in rows],
    }


@router.get("/summary")
def alert_summary():
    """Return operational alert counts."""

    generate_alerts()

    query = """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (
                WHERE status = 'open'
            ) AS open,
            COUNT(*) FILTER (
                WHERE status = 'open'
                  AND severity = 'high'
            ) AS high,
            COUNT(*) FILTER (
                WHERE status = 'open'
                  AND severity = 'medium'
            ) AS medium,
            COUNT(*) FILTER (
                WHERE status = 'open'
                  AND severity NOT IN ('high', 'medium')
            ) AS low
        FROM alerts
    """

    with engine.connect() as conn:
        row = conn.execute(text(query)).mappings().first()

    return dict(row)


@router.get("/{alert_id}")
def get_alert(alert_id: str):
    query = """
        SELECT
            id,
            category,
            ref_table,
            ref_id,
            message,
            severity,
            status,
            created_at
        FROM alerts
        WHERE id = :alert_id
    """

    with engine.connect() as conn:
        row = conn.execute(
            text(query),
            {"alert_id": alert_id},
        ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Alert not found",
        )

    return dict(row)
