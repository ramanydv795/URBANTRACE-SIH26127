import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import create_engine, text
from app.config import get_settings

engine = create_engine(
    get_settings().sync_database_url,
    pool_pre_ping=True,
)

now = datetime.now(timezone.utc)

with engine.begin() as conn:

    # Clean previous demo data
    conn.execute(text("DELETE FROM alerts"))
    conn.execute(text("DELETE FROM anomalies"))
    conn.execute(text("DELETE FROM review_queue"))
    conn.execute(text("DELETE FROM camera_transitions"))
    conn.execute(text("DELETE FROM reid_embeddings"))
    conn.execute(text("DELETE FROM vehicle_observations"))
    conn.execute(text("DELETE FROM vehicles"))
    conn.execute(text("DELETE FROM traffic_events"))
    conn.execute(text("DELETE FROM bottlenecks"))
    conn.execute(text("DELETE FROM od_matrix_daily"))
    conn.execute(text("DELETE FROM vehicle_journeys"))
    conn.execute(text("DELETE FROM trajectory_segments"))

    cameras = {
        r.code: r.id
        for r in conn.execute(
            text("SELECT id, code FROM cameras ORDER BY id")
        ).fetchall()
    }

    print(f"Loaded {len(cameras)} cameras")

    # DEMO vehicles
    vehicles = []

    for plate, vehicle_type, color in [
        ("CG04AB1234", "car", "white"),
        ("CG04CD5678", "car", "black"),
        ("CG04EF9012", "motorcycle", "red"),
    ]:
        vehicle_id = uuid.uuid4()

        conn.execute(
            text("""
                INSERT INTO vehicles
                (id, plate_best, plate_conf, vehicle_type, color,
                 first_seen, last_seen)
                VALUES
                (:id, :plate, 0.96, :type, :color, :ts, :ts)
            """),
            {
                "id": vehicle_id,
                "plate": plate,
                "type": vehicle_type,
                "color": color,
                "ts": now,
            },
        )

        vehicles.append(vehicle_id)

    # Camera journeys for demo
    routes = [
        ["C01", "C02", "C03", "C04"],
        ["C05", "C06", "C07", "C08"],
        ["C09", "C10", "C11", "C12"],
    ]

    for vehicle_id, route in zip(vehicles, routes):

        obs_ids = []

        for i, camera_code in enumerate(route):

            ts = now - timedelta(seconds=(len(route) - i) * 25)

            obs_id = uuid.uuid4()
            obs_ids.append(obs_id)

            conn.execute(
                text("""
                    INSERT INTO vehicle_observations
                    (
                        id,
                        camera_id,
                        vehicle_id,
                        ts,
                        track_id,
                        bbox,
                        frame_ref,
                        plate_text,
                        plate_conf,
                        vehicle_type,
                        type_conf,
                        color,
                        color_conf,
                        detection_conf
                    )
                    VALUES
                    (
                        :id,
                        :camera_id,
                        :vehicle_id,
                        :ts,
                        :track_id,
                        CAST(:bbox AS jsonb),
                        :frame_ref,
                        :plate,
                        0.96,
                        'car',
                        0.94,
                        'white',
                        0.91,
                        0.95
                    )
                """),
                {
                    "id": obs_id,
                    "camera_id": cameras[camera_code],
                    "vehicle_id": vehicle_id,
                    "ts": ts,
                    "track_id": i + 1,
                    "bbox": '{"x":120,"y":80,"w":160,"h":120}',
                    "frame_ref": f"demo://{camera_code}/frame_{i}",
                    "plate": "DEMO",
                },
            )

            conn.execute(
                text("""
                    INSERT INTO trajectory_segments
                    (
                        id,
                        vehicle_id,
                        from_camera_id,
                        to_camera_id,
                        segment_type,
                        path_camera_ids,
                        confidence
                    )
                    SELECT
                        :id,
                        :vehicle_id,
                        :from_camera,
                        :to_camera,
                        'observed',
                        ARRAY[:from_camera, :to_camera],
                        0.91
                    WHERE :from_camera IS NOT NULL
                      AND :to_camera IS NOT NULL
                """),
                {
                    "id": uuid.uuid4(),
                    "vehicle_id": vehicle_id,
                    "from_camera": cameras[route[i - 1]]
                    if i > 0 else cameras[camera_code],
                    "to_camera": cameras[camera_code],
                },
            )

        # Journey
        conn.execute(
            text("""
                INSERT INTO vehicle_journeys
                (
                    id,
                    vehicle_id,
                    start_ts,
                    end_ts,
                    start_zone_id,
                    end_zone_id,
                    distance_est_m,
                    duration_s,
                    avg_speed_kmh,
                    stop_count,
                    camera_count
                )
                VALUES
                (
                    :id,
                    :vehicle_id,
                    :start_ts,
                    :end_ts,
                    1,
                    2,
                    920,
                    75,
                    44.2,
                    0,
                    4
                )
            """),
            {
                "id": uuid.uuid4(),
                "vehicle_id": vehicle_id,
                "start_ts": now - timedelta(seconds=100),
                "end_ts": now - timedelta(seconds=25),
            },
        )

    print("Demo vehicles + observations + journeys created")

    # Demo traffic event
    conn.execute(
        text("""
            INSERT INTO traffic_events
            (
                id,
                type,
                start_ts,
                end_ts,
                affected_road_ids,
                is_simulated
            )
            VALUES
            (
                :id,
                'road_closure',
                :start_ts,
                :end_ts,
                ARRAY[1,2],
                TRUE
            )
        """),
        {
            "id": uuid.uuid4(),
            "start_ts": now - timedelta(minutes=10),
            "end_ts": now + timedelta(minutes=50),
        },
    )

    print("Demo traffic event created")

print("\nDEMO DATA READY")