"""
URBANTRACE Part 3 - Movement Graph

NetworkX query layer over camera transitions and camera topology.

This module does not perform association.
It only builds/query graphs from persisted data.
"""

from __future__ import annotations

from typing import Any

import networkx as nx
from sqlalchemy import create_engine, text

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings


class MovementGraph:
    def __init__(self):
        settings = get_settings()

        self.engine = create_engine(
            settings.sync_database_url,
            pool_pre_ping=True,
        )

    # ------------------------------------------------------------------
    # Vehicle subgraph
    # ------------------------------------------------------------------

    def build_vehicle_subgraph(
        self,
        vehicle_id: str,
    ) -> nx.MultiDiGraph:

        graph = nx.MultiDiGraph()

        query = text(
            """
            SELECT
                ct.id AS transition_id,
                ct.vehicle_id,
                ct.from_observation_id,
                ct.to_observation_id,
                ct.status,
                ct.evidence,

                from_vo.ts AS from_ts,
                to_vo.ts AS to_ts,

                from_camera.code AS from_camera_code,
                to_camera.code AS to_camera_code

            FROM camera_transitions ct

            JOIN vehicle_observations from_vo
                ON from_vo.id = ct.from_observation_id

            JOIN vehicle_observations to_vo
                ON to_vo.id = ct.to_observation_id

            JOIN cameras from_camera
                ON from_camera.id = from_vo.camera_id

            JOIN cameras to_camera
                ON to_camera.id = to_vo.camera_id

            WHERE ct.vehicle_id = :vehicle_id

            ORDER BY from_vo.ts ASC
            """
        )

        with self.engine.connect() as connection:
            rows = connection.execute(
                query,
                {"vehicle_id": vehicle_id},
            ).mappings().all()

        for row in rows:

            from_camera = row["from_camera_code"]
            to_camera = row["to_camera_code"]

            graph.add_node(
                from_camera,
                camera_code=from_camera,
                timestamp=row["from_ts"],
            )

            graph.add_node(
                to_camera,
                camera_code=to_camera,
                timestamp=row["to_ts"],
            )

            graph.add_edge(
                from_camera,
                to_camera,
                key=str(row["transition_id"]),
                transition_id=str(row["transition_id"]),
                vehicle_id=(
                    str(row["vehicle_id"])
                    if row["vehicle_id"] is not None
                    else None
                ),
                from_observation_id=str(
                    row["from_observation_id"]
                ),
                to_observation_id=str(
                    row["to_observation_id"]
                ),
                status=row["status"],
                evidence=row["evidence"],
                from_ts=row["from_ts"],
                to_ts=row["to_ts"],
            )

        return graph

    # ------------------------------------------------------------------
    # Journey hops
    # ------------------------------------------------------------------

    def vehicle_journey_hops(
        self,
        vehicle_id: str,
    ) -> list[dict[str, Any]]:

        query = text(
            """
            SELECT
                ct.id AS transition_id,
                ct.from_observation_id,
                ct.to_observation_id,
                ct.status,
                ct.evidence,

                from_vo.ts AS from_ts,
                to_vo.ts AS to_ts,

                from_camera.code AS from_camera_code,
                to_camera.code AS to_camera_code

            FROM camera_transitions ct

            JOIN vehicle_observations from_vo
                ON from_vo.id = ct.from_observation_id

            JOIN vehicle_observations to_vo
                ON to_vo.id = ct.to_observation_id

            JOIN cameras from_camera
                ON from_camera.id = from_vo.camera_id

            JOIN cameras to_camera
                ON to_camera.id = to_vo.camera_id

            WHERE ct.vehicle_id = :vehicle_id
              AND ct.status = 'auto_linked'

            ORDER BY from_vo.ts ASC
            """
        )

        with self.engine.connect() as connection:
            rows = connection.execute(
                query,
                {"vehicle_id": vehicle_id},
            ).mappings().all()

        result = []

        for row in rows:
            result.append(
                {
                    "transition_id": str(
                        row["transition_id"]
                    ),
                    "from_observation_id": str(
                        row["from_observation_id"]
                    ),
                    "to_observation_id": str(
                        row["to_observation_id"]
                    ),
                    "from_camera": row[
                        "from_camera_code"
                    ],
                    "to_camera": row[
                        "to_camera_code"
                    ],
                    "from_ts": row["from_ts"],
                    "to_ts": row["to_ts"],
                    "status": row["status"],
                    "evidence": row["evidence"],
                }
            )

        return result

    # ------------------------------------------------------------------
    # Full static topology graph
    # ------------------------------------------------------------------

    def build_full_topology_graph(
        self,
    ) -> nx.DiGraph:

        graph = nx.DiGraph()

        query = text(
            """
            SELECT
                ct.*,
                c_from.code AS from_camera_code,
                c_to.code AS to_camera_code

            FROM camera_topology ct

            JOIN cameras c_from
                ON c_from.id = ct.from_camera_id

            JOIN cameras c_to
                ON c_to.id = ct.to_camera_id
            """
        )

        try:
            with self.engine.connect() as connection:
                rows = connection.execute(
                    query
                ).mappings().all()
        except Exception:
            return graph

        for row in rows:

            from_camera = row[
                "from_camera_code"
            ]

            to_camera = row[
                "to_camera_code"
            ]

            graph.add_edge(
                from_camera,
                to_camera,
                **dict(row),
            )

        return graph

    # ------------------------------------------------------------------
    # Reachability
    # ------------------------------------------------------------------

    def is_reachable(
        self,
        from_camera: str,
        to_camera: str,
    ) -> bool:

        graph = self.build_full_topology_graph()

        if (
            from_camera not in graph
            or to_camera not in graph
        ):
            return False

        return nx.has_path(
            graph,
            from_camera,
            to_camera,
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        self.engine.dispose()


__all__ = [
    "MovementGraph",
]