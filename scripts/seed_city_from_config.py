"""
Seeds the relational city tables from configs/demo_city.yaml.

The demo_city.yaml file remains the source of truth for the demo topology,
while PostgreSQL stores relational rows needed by the perception pipeline.

Idempotent: safe to run multiple times.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import get_demo_city, get_settings  # noqa: E402


def polygon_wkt(polygon: list[list[float]]) -> str:
    coords = ", ".join(f"{lng} {lat}" for lat, lng in polygon)

    # Ensure polygon is closed.
    if polygon and polygon[0] != polygon[-1]:
        first_lat, first_lng = polygon[0]
        coords += f", {first_lng} {first_lat}"

    return f"SRID=4326;POLYGON(({coords}))"


def point_wkt(lat: float, lng: float) -> str:
    return f"SRID=4326;POINT({lng} {lat})"


def linestring_wkt(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
) -> str:
    return f"SRID=4326;LINESTRING({lng1} {lat1}, {lng2} {lat2})"


def seed() -> None:
    settings = get_settings()
    city = get_demo_city()

    engine = create_engine(settings.sync_database_url)

    intersections_by_code = {
        item["code"]: item
        for item in city["intersections"]
    }

    with engine.begin() as conn:

        # ---------------------------------------------------------
        # Zones
        # ---------------------------------------------------------
        for zone in city["zones"]:
            conn.execute(
                text(
                    """
                    INSERT INTO zones
                        (code, name, geom)
                    VALUES
                        (:code, :name, ST_GeomFromEWKT(:geom))
                    ON CONFLICT (code) DO NOTHING
                    """
                ),
                {
                    "code": zone["code"],
                    "name": zone["name"],
                    "geom": polygon_wkt(zone["polygon"]),
                },
            )

        # ---------------------------------------------------------
        # Intersections
        # ---------------------------------------------------------
        for intersection in city["intersections"]:
            conn.execute(
                text(
                    """
                    INSERT INTO intersections
                        (code, name, geom)
                    VALUES
                        (:code, :name, ST_GeomFromEWKT(:geom))
                    ON CONFLICT (code) DO NOTHING
                    """
                ),
                {
                    "code": intersection["code"],
                    "name": intersection["name"],
                    "geom": point_wkt(
                        intersection["lat"],
                        intersection["lng"],
                    ),
                },
            )

        # ---------------------------------------------------------
        # Roads
        # ---------------------------------------------------------
        for road in city["roads"]:
            start = intersections_by_code[
                road["from_intersection"]
            ]
            end = intersections_by_code[
                road["to_intersection"]
            ]

            conn.execute(
                text(
                    """
                    INSERT INTO roads
                        (
                            code,
                            name,
                            road_class,
                            geom,
                            capacity_est,
                            length_m
                        )
                    VALUES
                        (
                            :code,
                            :name,
                            :road_class,
                            ST_GeomFromEWKT(:geom),
                            :capacity_est,
                            :length_m
                        )
                    ON CONFLICT (code) DO NOTHING
                    """
                ),
                {
                    "code": road["code"],
                    "name": road["name"],
                    "road_class": road["road_class"],
                    "geom": linestring_wkt(
                        start["lat"],
                        start["lng"],
                        end["lat"],
                        end["lng"],
                    ),
                    "capacity_est": road["capacity_est"],
                    "length_m": road["length_m"],
                },
            )

        road_id_by_code = {
            row.code: row.id
            for row in conn.execute(
                text("SELECT id, code FROM roads")
            )
        }

        zone_id_by_code = {
            row.code: row.id
            for row in conn.execute(
                text("SELECT id, code FROM zones")
            )
        }

        # ---------------------------------------------------------
        # Cameras
        # ---------------------------------------------------------
        for camera in city["cameras"]:
            conn.execute(
                text(
                    """
                    INSERT INTO cameras
                        (
                            code,
                            name,
                            geom,
                            road_id,
                            zone_id,
                            direction_deg,
                            status,
                            video_source
                        )
                    VALUES
                        (
                            :code,
                            :name,
                            ST_GeomFromEWKT(:geom),
                            :road_id,
                            :zone_id,
                            :direction_deg,
                            'offline',
                            :video_source
                        )
                    ON CONFLICT (code) DO NOTHING
                    """
                ),
                {
                    "code": camera["code"],
                    "name": camera["name"],
                    "geom": point_wkt(
                        camera["lat"],
                        camera["lng"],
                    ),
                    "road_id": road_id_by_code[camera["road"]],
                    "zone_id": zone_id_by_code[camera["zone"]],
                    "direction_deg": camera["direction_deg"],
                    "video_source": camera["video_source"],
                },
            )

        camera_id_by_code = {
            row.code: row.id
            for row in conn.execute(
                text("SELECT id, code FROM cameras")
            )
        }

        # ---------------------------------------------------------
        # Camera topology
        # ---------------------------------------------------------
        for topology in city["camera_topology"]:
            conn.execute(
                text(
                    """
                    INSERT INTO camera_topology
                        (
                            from_camera_id,
                            to_camera_id,
                            distance_m,
                            min_travel_s,
                            max_travel_s,
                            typical_travel_s
                        )
                    VALUES
                        (
                            :from_id,
                            :to_id,
                            :distance_m,
                            :min_s,
                            :max_s,
                            :typ_s
                        )
                    ON CONFLICT
                        (from_camera_id, to_camera_id)
                    DO NOTHING
                    """
                ),
                {
                    "from_id": camera_id_by_code[
                        topology["from_camera"]
                    ],
                    "to_id": camera_id_by_code[
                        topology["to_camera"]
                    ],
                    "distance_m": topology["distance_m"],
                    "min_s": topology["min_travel_s"],
                    "max_s": topology["max_travel_s"],
                    "typ_s": topology["typical_travel_s"],
                },
            )

    print(
        f"Seeded "
        f"{len(city['zones'])} zones, "
        f"{len(city['roads'])} roads, "
        f"{len(city['intersections'])} intersections, "
        f"{len(city['cameras'])} cameras, "
        f"{len(city['camera_topology'])} topology edges."
    )


if __name__ == "__main__":
    seed()