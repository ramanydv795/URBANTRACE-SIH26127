-- =========================================================
-- URBANTRACE DATABASE SCHEMA
-- PostgreSQL + PostGIS
-- Part 1: Foundation schema. Extended in later parts as needed.
-- =========================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------
-- SPATIAL REFERENCE / CITY MODEL
-- ---------------------------------------------------------

CREATE TABLE zones (
    id              SERIAL PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL,       -- e.g. 'ZONE_A'
    name            TEXT NOT NULL,
    geom            GEOMETRY(POLYGON, 4326) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_zones_geom ON zones USING GIST (geom);

CREATE TABLE roads (
    id              SERIAL PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL,       -- e.g. 'ROAD_04'
    name            TEXT NOT NULL,
    road_class      TEXT NOT NULL DEFAULT 'arterial', -- arterial | collector | local
    geom            GEOMETRY(LINESTRING, 4326) NOT NULL,
    capacity_est    INTEGER,                    -- vehicles/hour, estimated
    length_m        NUMERIC,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_roads_geom ON roads USING GIST (geom);

CREATE TABLE intersections (
    id              SERIAL PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL,       -- e.g. 'J04'
    name            TEXT NOT NULL,
    geom            GEOMETRY(POINT, 4326) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_intersections_geom ON intersections USING GIST (geom);

CREATE TABLE cameras (
    id              SERIAL PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL,       -- e.g. 'C07'
    name            TEXT NOT NULL,
    geom            GEOMETRY(POINT, 4326) NOT NULL,
    road_id         INTEGER REFERENCES roads(id),
    zone_id         INTEGER REFERENCES zones(id),
    direction_deg   NUMERIC,                    -- facing direction, degrees
    status          TEXT NOT NULL DEFAULT 'offline', -- online | degraded | offline
    fov_meta        JSONB DEFAULT '{}'::jsonb,
    video_source    TEXT,                       -- path/URI used in demo mode
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cameras_geom ON cameras USING GIST (geom);
CREATE INDEX idx_cameras_status ON cameras (status);

-- Static reachability graph between cameras: the "possibility space"
-- used by association, recovery, and prediction modules.
CREATE TABLE camera_topology (
    id                  SERIAL PRIMARY KEY,
    from_camera_id      INTEGER NOT NULL REFERENCES cameras(id),
    to_camera_id        INTEGER NOT NULL REFERENCES cameras(id),
    road_path_ids       INTEGER[] DEFAULT '{}',     -- roads(id) sequence
    distance_m          NUMERIC,
    min_travel_s        INTEGER NOT NULL,
    max_travel_s        INTEGER NOT NULL,
    typical_travel_s     INTEGER NOT NULL,
    historical_freq     INTEGER NOT NULL DEFAULT 0, -- learned transition frequency
    UNIQUE (from_camera_id, to_camera_id)
);
CREATE INDEX idx_topology_from ON camera_topology (from_camera_id);
CREATE INDEX idx_topology_to ON camera_topology (to_camera_id);

-- ---------------------------------------------------------
-- PERCEPTION OUTPUT
-- ---------------------------------------------------------

CREATE TABLE vehicles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plate_best      TEXT,
    plate_conf      NUMERIC,
    vehicle_type    TEXT,
    color           TEXT,
    is_blacklisted  BOOLEAN NOT NULL DEFAULT false,
    first_seen      TIMESTAMPTZ,
    last_seen       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vehicles_plate ON vehicles (plate_best);
CREATE INDEX idx_vehicles_blacklist ON vehicles (is_blacklisted) WHERE is_blacklisted;

CREATE TABLE vehicle_observations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id       INTEGER NOT NULL REFERENCES cameras(id),
    vehicle_id      UUID REFERENCES vehicles(id),   -- nullable until associated
    ts              TIMESTAMPTZ NOT NULL,
    track_id        INTEGER,                        -- intra-camera ByteTrack id
    bbox            JSONB NOT NULL,                  -- {x,y,w,h}
    frame_ref       TEXT,                            -- path/ref to saved crop/frame
    plate_text      TEXT,
    plate_conf      NUMERIC,
    vehicle_type    TEXT,
    type_conf       NUMERIC,
    color           TEXT,
    color_conf      NUMERIC,
    detection_conf  NUMERIC,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_obs_camera_ts ON vehicle_observations (camera_id, ts);
CREATE INDEX idx_obs_vehicle ON vehicle_observations (vehicle_id);
CREATE INDEX idx_obs_plate ON vehicle_observations (plate_text);

CREATE TABLE reid_embeddings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    observation_id  UUID NOT NULL REFERENCES vehicle_observations(id) ON DELETE CASCADE,
    model_version   TEXT NOT NULL,
    vector          NUMERIC[] NOT NULL,   -- swapped for pgvector in a later part if enabled
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reid_observation ON reid_embeddings (observation_id);

-- ---------------------------------------------------------
-- GRAPH / ASSOCIATION
-- ---------------------------------------------------------

CREATE TABLE camera_transitions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id          UUID REFERENCES vehicles(id),
    from_observation_id UUID NOT NULL REFERENCES vehicle_observations(id),
    to_observation_id   UUID NOT NULL REFERENCES vehicle_observations(id),
    travel_time_s       NUMERIC,
    est_speed_kmh       NUMERIC,
    direction_ok        BOOLEAN,
    topology_ok         BOOLEAN,
    time_feasible       BOOLEAN,
    plate_similarity    NUMERIC,
    reid_similarity     NUMERIC,
    confidence          NUMERIC NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending_review', -- auto_linked | pending_review | rejected
    evidence            JSONB DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_transitions_vehicle ON camera_transitions (vehicle_id);
CREATE INDEX idx_transitions_status ON camera_transitions (status);

CREATE TABLE trajectory_segments (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id          UUID NOT NULL REFERENCES vehicles(id),
    from_camera_id      INTEGER NOT NULL REFERENCES cameras(id),
    to_camera_id        INTEGER NOT NULL REFERENCES cameras(id),
    segment_type        TEXT NOT NULL,   -- observed | inferred
    path_camera_ids     INTEGER[] DEFAULT '{}',
    confidence          NUMERIC,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_segments_vehicle ON trajectory_segments (vehicle_id);

CREATE TABLE vehicle_journeys (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id          UUID NOT NULL REFERENCES vehicles(id),
    start_ts            TIMESTAMPTZ,
    end_ts              TIMESTAMPTZ,
    start_zone_id       INTEGER REFERENCES zones(id),
    end_zone_id         INTEGER REFERENCES zones(id),
    distance_est_m      NUMERIC,
    duration_s          NUMERIC,
    avg_speed_kmh       NUMERIC,
    stop_count          INTEGER DEFAULT 0,
    camera_count        INTEGER DEFAULT 0,
    anomaly_score       NUMERIC DEFAULT 0,
    congestion_exposure NUMERIC DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_journeys_vehicle ON vehicle_journeys (vehicle_id);

-- ---------------------------------------------------------
-- TRAFFIC STATE / ANALYTICS
-- ---------------------------------------------------------

CREATE TABLE traffic_snapshots (
    id                  BIGSERIAL PRIMARY KEY,
    road_id             INTEGER NOT NULL REFERENCES roads(id),
    ts                  TIMESTAMPTZ NOT NULL,
    vehicle_count       INTEGER NOT NULL DEFAULT 0,
    avg_speed_kmh       NUMERIC,
    density             NUMERIC,             -- vehicles per km
    congestion_level    TEXT                 -- free | moderate | heavy | severe
);
CREATE INDEX idx_snapshots_road_ts ON traffic_snapshots (road_id, ts);

CREATE TABLE od_matrix_daily (
    id                  SERIAL PRIMARY KEY,
    date                DATE NOT NULL,
    origin_zone_id      INTEGER NOT NULL REFERENCES zones(id),
    dest_zone_id        INTEGER NOT NULL REFERENCES zones(id),
    trip_count          INTEGER NOT NULL DEFAULT 0,
    UNIQUE (date, origin_zone_id, dest_zone_id)
);

CREATE TABLE bottlenecks (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    intersection_id     INTEGER REFERENCES intersections(id),
    road_id             INTEGER REFERENCES roads(id),
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    indicators          JSONB DEFAULT '{}'::jsonb,
    explanation         TEXT,
    severity            TEXT   -- low | medium | high
);

-- ---------------------------------------------------------
-- EVENTS / ANOMALIES / ALERTS
-- ---------------------------------------------------------

CREATE TABLE traffic_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type                TEXT NOT NULL,   -- accident | closure | construction | event | weather
    geom                GEOMETRY(POINT, 4326),
    start_ts            TIMESTAMPTZ NOT NULL,
    end_ts              TIMESTAMPTZ,
    affected_road_ids   INTEGER[] DEFAULT '{}',
    is_simulated        BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_events_geom ON traffic_events USING GIST (geom);

CREATE TABLE anomalies (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id          UUID REFERENCES vehicles(id),
    journey_id          UUID REFERENCES vehicle_journeys(id),
    type                TEXT NOT NULL,
    reason              TEXT NOT NULL,
    evidence            JSONB DEFAULT '{}'::jsonb,
    confidence          NUMERIC,
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_anomalies_vehicle ON anomalies (vehicle_id);

CREATE TABLE alerts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category            TEXT NOT NULL,   -- blacklist | anomaly | camera_failure | congestion | low_confidence
    ref_table           TEXT,
    ref_id              TEXT,
    message             TEXT NOT NULL,
    severity            TEXT NOT NULL DEFAULT 'medium',
    status              TEXT NOT NULL DEFAULT 'open',  -- open | acknowledged | resolved
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_alerts_status ON alerts (status);
CREATE INDEX idx_alerts_category ON alerts (category);

-- ---------------------------------------------------------
-- SIMULATION
-- ---------------------------------------------------------

CREATE TABLE simulation_scenarios (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                TEXT NOT NULL,
    type                TEXT NOT NULL,   -- closure | diversion | camera_failure
    params              JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE simulation_results (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scenario_id         UUID NOT NULL REFERENCES simulation_scenarios(id),
    before_metrics      JSONB NOT NULL,
    after_metrics       JSONB NOT NULL,
    affected_road_ids   INTEGER[] DEFAULT '{}',
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------
-- GOVERNANCE
-- ---------------------------------------------------------

CREATE TABLE review_queue (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_transition_id    UUID NOT NULL REFERENCES camera_transitions(id),
    status                  TEXT NOT NULL DEFAULT 'pending', -- pending | accepted | rejected
    reviewer                TEXT,
    reviewed_at             TIMESTAMPTZ,
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_review_status ON review_queue (status);

CREATE TABLE audit_logs (
    id                  BIGSERIAL PRIMARY KEY,
    actor               TEXT NOT NULL,
    action              TEXT NOT NULL,
    ref_table           TEXT,
    ref_id              TEXT,
    before              JSONB,
    after               JSONB,
    ts                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_ts ON audit_logs (ts);

-- ---------------------------------------------------------
-- CAMERA HEALTH (observability, written by the perception workers)
-- ---------------------------------------------------------

CREATE TABLE camera_health_metrics (
    id                  BIGSERIAL PRIMARY KEY,
    camera_id           INTEGER NOT NULL REFERENCES cameras(id),
    ts                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    fps                 NUMERIC,
    processing_latency_ms NUMERIC,
    detection_count     INTEGER,
    ocr_success_rate    NUMERIC,
    stream_health       TEXT   -- ok | degraded | down
);
CREATE INDEX idx_health_camera_ts ON camera_health_metrics (camera_id, ts);
