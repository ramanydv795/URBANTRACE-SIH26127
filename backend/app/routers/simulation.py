from fastapi import APIRouter
from pydantic import BaseModel, Field

from graph_engine.simulation import run_simulation


router = APIRouter(
    prefix="/api/simulation",
    tags=["simulation"],
)


class SimulationRequest(BaseModel):
    name: str
    scenario_type: str
    affected_road_ids: list[int] = Field(default_factory=list)
    created_by: str = "user"


@router.post("")
def create_simulation(request: SimulationRequest):
    return run_simulation(
        name=request.name,
        scenario_type=request.scenario_type,
        params={
            "affected_road_ids": request.affected_road_ids,
        },
        created_by=request.created_by,
    )