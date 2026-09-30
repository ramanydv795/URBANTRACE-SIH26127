from fastapi import APIRouter, Query

from graph_engine.traffic import build_od_matrix, detect_bottlenecks

router = APIRouter(prefix="/api/traffic", tags=["traffic"])


@router.get("/od-matrix")
def get_od_matrix(
    date: str | None = Query(default=None)
):
    rows = build_od_matrix()

    if date:
        rows = [
            row for row in rows
            if str(row["date"]) == date
        ]

    return {
        "count": len(rows),
        "items": rows,
    }


@router.get("/bottlenecks")
def get_bottlenecks():
    items = detect_bottlenecks()

    return {
        "count": len(items),
        "items": items,
    }