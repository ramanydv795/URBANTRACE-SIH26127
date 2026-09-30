"""
Generates configs/demo_city.yaml: a synthetic 4x3 grid city used for the
URBANTRACE demo. Deterministic so the same city is regenerated every time.

Run:
    python scripts/generate_demo_city.py
"""

import math
import yaml
from pathlib import Path

# Grid dimensions
COLS = 4
ROWS = 3
# Base coordinate (arbitrary synthetic origin — not a real surveilled location)
BASE_LAT = 12.9716
BASE_LNG = 77.5946
STEP_DEG = 0.006  # ~650m spacing between intersections

OUT_PATH = Path(__file__).resolve().parent.parent / "configs" / "demo_city.yaml"


def intersection_code(r, c):
    return f"J{r * COLS + c:02d}"


def build():
    intersections = []
    coord = {}
    for r in range(ROWS):
        for c in range(COLS):
            code = intersection_code(r, c)
            lat = BASE_LAT + r * STEP_DEG
            lng = BASE_LNG + c * STEP_DEG
            coord[code] = (lat, lng)
            intersections.append({
                "code": code,
                "name": f"Junction {code}",
                "lat": round(lat, 6),
                "lng": round(lng, 6),
            })

    # Zones: 2x2 super-blocks over the grid (6 zones from a 4x3 grid -> use 4 quadrants + 2 edge zones)
    zones = [
        {"code": "ZONE_A", "name": "North-West District", "cols": [0, 1], "rows": [0]},
        {"code": "ZONE_B", "name": "North-East District", "cols": [2, 3], "rows": [0]},
        {"code": "ZONE_C", "name": "Central District", "cols": [1, 2], "rows": [1]},
        {"code": "ZONE_D", "name": "West Corridor", "cols": [0], "rows": [1, 2]},
        {"code": "ZONE_E", "name": "South District", "cols": [1, 2, 3], "rows": [2]},
        {"code": "ZONE_F", "name": "East Corridor", "cols": [3], "rows": [1]},
    ]
    zone_polys = []
    pad = STEP_DEG * 0.45
    for z in zones:
        lats = [BASE_LAT + r * STEP_DEG for r in z["rows"]]
        lngs = [BASE_LNG + c * STEP_DEG for c in z["cols"]]
        min_lat, max_lat = min(lats) - pad, max(lats) + pad
        min_lng, max_lng = min(lngs) - pad, max(lngs) + pad
        zone_polys.append({
            "code": z["code"],
            "name": z["name"],
            "polygon": [
                [min_lat, min_lng], [min_lat, max_lng],
                [max_lat, max_lng], [max_lat, min_lng],
                [min_lat, min_lng],
            ],
        })

    def zone_for(r, c):
        for z in zones:
            if c in z["cols"] and r in z["rows"]:
                return z["code"]
        return zones[-1]["code"]

    # Roads: horizontal + vertical segments between adjacent intersections
    roads = []
    road_id = 1

    def add_road(a, b, road_class="arterial"):
        nonlocal road_id
        lat1, lng1 = coord[a]
        lat2, lng2 = coord[b]
        dist_m = haversine_m(lat1, lng1, lat2, lng2)
        code = f"ROAD_{road_id:02d}"
        roads.append({
            "code": code,
            "name": f"{a}-{b} Link",
            "road_class": road_class,
            "from_intersection": a,
            "to_intersection": b,
            "length_m": round(dist_m, 1),
            "capacity_est": 1800 if road_class == "arterial" else 1000,
        })
        road_id += 1
        return code

    for r in range(ROWS):
        for c in range(COLS - 1):
            add_road(intersection_code(r, c), intersection_code(r, c + 1))
    for r in range(ROWS - 1):
        for c in range(COLS):
            add_road(intersection_code(r, c), intersection_code(r + 1, c), road_class="collector")

    # Cameras: one per road, placed at the midpoint, plus a few extra on
    # long arterials to reach ~22 cameras total.
    cameras = []
    cam_id = 1

    def add_camera(road, frac=0.5):
        nonlocal cam_id
        lat1, lng1 = coord[road["from_intersection"]]
        lat2, lng2 = coord[road["to_intersection"]]
        lat = lat1 + (lat2 - lat1) * frac
        lng = lng1 + (lng2 - lng1) * frac
        code = f"C{cam_id:02d}"
        r0, c0 = divmod(int(road["from_intersection"][1:]), COLS)
        zone = zone_for(r0, c0)
        cameras.append({
            "code": code,
            "name": f"Camera {code} ({road['code']})",
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "road": road["code"],
            "zone": zone,
            "direction_deg": bearing(lat1, lng1, lat2, lng2),
            "video_source": f"data/demo_streams/{code.lower()}.mp4",
        })
        cam_id += 1

    for road in roads:
        add_camera(road, frac=0.5)
        if road["road_class"] == "arterial" and cam_id <= 22:
            add_camera(road, frac=0.85)

    cameras = cameras[:25]

    # Topology: connect cameras that lie on roads meeting at the same
    # intersection (i.e. reachable without passing another camera first).
    topology = []
    cams_by_junction = {}
    for road in roads:
        for junc in (road["from_intersection"], road["to_intersection"]):
            cams_by_junction.setdefault(junc, set()).add(road["code"])

    cam_by_road = {}
    for cam in cameras:
        cam_by_road.setdefault(cam["road"], []).append(cam)

    seen_pairs = set()
    for junc, road_codes in cams_by_junction.items():
        cams_here = []
        for rc in road_codes:
            cams_here.extend(cam_by_road.get(rc, []))
        for a in cams_here:
            for b in cams_here:
                if a["code"] == b["code"]:
                    continue
                pair = (a["code"], b["code"])
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                dist = haversine_m(a["lat"], a["lng"], b["lat"], b["lng"])
                avg_speed_kmh = 30
                typical_s = max(20, int(dist / (avg_speed_kmh * 1000 / 3600)))
                topology.append({
                    "from_camera": a["code"],
                    "to_camera": b["code"],
                    "distance_m": round(dist, 1),
                    "min_travel_s": max(10, int(typical_s * 0.6)),
                    "max_travel_s": int(typical_s * 1.8),
                    "typical_travel_s": typical_s,
                })

    doc = {
        "city_name": "Demo City (URBANTRACE synthetic grid)",
        "grid": {"rows": ROWS, "cols": COLS, "step_deg": STEP_DEG},
        "zones": zone_polys,
        "intersections": intersections,
        "roads": roads,
        "cameras": cameras,
        "camera_topology": topology,
    }
    return doc


def haversine_m(lat1, lng1, lat2, lng2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def bearing(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lng2 - lng1)
    x = math.sin(dlmb) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlmb)
    return round((math.degrees(math.atan2(x, y)) + 360) % 360, 1)


if __name__ == "__main__":
    doc = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        yaml.dump(doc, f, sort_keys=False, allow_unicode=True)
    n_cam = len(doc["cameras"])
    n_road = len(doc["roads"])
    n_topo = len(doc["camera_topology"])
    print(f"Wrote {OUT_PATH} — {n_cam} cameras, {n_road} roads, {n_topo} topology edges.")
