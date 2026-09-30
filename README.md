# URBANTRACE — Part 1: Foundation

City-wide AI engine for multi-camera ANPR trajectory tracking and urban
traffic analytics (SIH26127 / BEL). This is Part 1 of the build: repo
scaffold, database schema, demo city config, a working FastAPI backend, and
a working React frontend shell with all 9 pages routed.

**No fake data.** Every number shown in the UI right now comes from a real
API call. Cameras show `offline` because no perception worker is attached
yet — that happens in Part 2.

---

## 1. What's in Part 1

```
urbantrace/
  backend/            FastAPI app (health, cameras, city, system routers)
  database/schema.sql  Full PostgreSQL + PostGIS schema
  configs/demo_city.yaml   Generated synthetic demo city (25 cams, 17 roads, 6 zones)
  scripts/generate_demo_city.py   Regenerates the demo city deterministically
  frontend/           React + TypeScript + Vite + Tailwind, 9 routed pages
  docker/docker-compose.yml   Postgres+PostGIS, Redis, backend
  .env.example
```

## 2. Prerequisites

- Docker + Docker Compose
- Node.js 18+ and npm (for running the frontend dev server)
- Python 3.11+ (only if you want to run the backend outside Docker)

## 3. Run everything with Docker (recommended)

```bash
cd urbantrace
cp .env.example .env
docker compose -f docker/docker-compose.yml up --build
```

This starts:
- `postgres` on `localhost:5432` (schema auto-applied from `database/schema.sql` on first boot)
- `redis` on `localhost:6379`
- `backend` (FastAPI) on `localhost:8000`

Check it's alive:

```bash
curl http://localhost:8000/api/health
# {"status":"ok","service":"urbantrace-api"}

curl http://localhost:8000/api/health/detailed
# checks DB, Redis, and demo_city.yaml load all at once

curl http://localhost:8000/api/city/summary
# {"city_name":"Demo City (URBANTRACE synthetic grid)","zones":6,"roads":17,
#  "intersections":12,"cameras":25,"topology_edges":160}
```

Interactive API docs: `http://localhost:8000/docs`

## 4. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api/*` to
`http://localhost:8000`, so the backend must be running first.

You should see:
- **Command Center** — real camera/road/zone counts and a live API-connected indicator in the top bar.
- **Camera Health** — all 25 demo cameras listed, status `offline` (accurate — no perception worker yet).
- The other 7 pages (Live Map, Vehicle Journey, Trajectory Explainer, Traffic Analytics, What-If Simulator, Alert Center, Event Replay) show a placeholder explaining which upcoming Part wires them up.

## 5. Run the backend without Docker (optional)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Postgres + Redis must be reachable per your .env (e.g. via `docker compose up postgres redis`)
uvicorn app.main:app --reload
```

## 6. Regenerating the demo city

The demo city is deterministic and versioned as YAML, not hand-maintained:

```bash
pip install pyyaml
python scripts/generate_demo_city.py
```

## 7. What was tested for this part

- Frontend: `tsc -b` (type-check) and `vite build` (production build) both pass cleanly.
- Backend: app imports cleanly, and `/api/health`, `/api/city/summary`, `/api/cameras` were exercised directly against the generated `demo_city.yaml` and return correct real data.
- Not yet tested here (needs Docker): Postgres schema apply and `/api/health/detailed` DB/Redis checks — verify these the first time you run `docker compose up`.

## Part 1 Project State

**Implemented:** repo scaffold, Docker Compose, full DB schema, demo city generator + config, FastAPI skeleton with health/camera/city/system routers, React frontend shell with routing, theme, and 9 pages (2 wired to real data, 7 stubbed with clear "coming in Part X" labels).

**Files created:** see tree above — `backend/`, `database/schema.sql`, `configs/demo_city.yaml`, `scripts/generate_demo_city.py`, `frontend/`, `docker/docker-compose.yml`, `.env.example`, this `README.md`.

**Files modified:** none (first part).

**Next:** `PART 2` — perception pipeline: YOLO detection + ByteTrack, ANPR (PaddleOCR), color/type attributes, Re-ID embeddings, writing real `vehicle_observations` rows from a sample video.
