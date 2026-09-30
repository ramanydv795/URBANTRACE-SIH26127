"""
URBANTRACE Part 4.1 - Missing-Trajectory Recovery

Finds likely vehicle-chain gaps between two observations that are
not directly connected by an observed camera transition.

Important:
- Does NOT create fake observations.
- Uses the seeded camera topology graph.
- Uses NetworkX shortest-simple paths.
- Uses time plausibility, path popularity, plate similarity,
  and Re-ID similarity when available.
- Missing signals are excluded and remaining weights are renormalized.
- DB writes are kept in isolated methods so the recovery logic
  can be tested safely first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID
import uuid

import networkx as nx
from sqlalchemy import create_engine, text

from app.config import get_settings


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

RECOVERY_THRESHOLD = 0.70

# Maximum allowed gap between endpoint A and endpoint B.
MAX_GAP_S = 20 * 60

# Maximum number of candidate paths examined for one recovery.
K_PATHS = 5

BASE_WEIGHTS = {
    "time": 0.35,
    "popularity": 0.15,
    "plate": 0.25,
    "reid": 0.25,
}


# ---------------------------------------------------------------------
# Result contract
# ---------------------------------------------------------------------

@dataclass
class RecoveryResult:
    source_vehicle_id: UUID
    target_vehicle_id: UUID

    from_camera_id: int
    to_camera_id: int

    path_camera_ids: list[int]

    confidence: float
    status: str

    time_score: Optional[float]
    popularity_score: Optional[float]
    plate_score: Optional[float]
    reid_score: Optional[float]

    evidence: dict[str, Any]


# ---------------------------------------------------------------------
# Recovery engine
# ---------------------------------------------------------------------

class RecoveryEngine:
    def __init__(self) -> None:
        settings = get_settings()

        self.engine = create_engine(
            settings.sync_database_url,
            pool_pre_ping=True,
        )

        self.graph = self._build_topology_graph()

    # -----------------------------------------------------------------
    # Topology
    # -----------------------------------------------------------------

    def _build_topology_graph(self) -> nx.DiGraph:
        """
        Build the static camera topology graph.

        Edge weight is typical travel time.
        """

        graph = nx.DiGraph()

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        from_camera_id,
                        to_camera_id,
                        distance_m,
                        min_travel_s,
                        max_travel_s,
                        typical_travel_s,
                        historical_freq
                    FROM camera_topology
                    """
                )
            ).mappings().all()

        for row in rows:
            graph.add_edge(
                int(row["from_camera_id"]),
                int(row["to_camera_id"]),
                distance_m=float(row["distance_m"] or 0),
                min_travel_s=int(row["min_travel_s"] or 0),
                max_travel_s=int(row["max_travel_s"] or 0),
                typical_travel_s=int(row["typical_travel_s"] or 0),
                historical_freq=int(row["historical_freq"] or 0),
            )

        return graph

    # -----------------------------------------------------------------
    # Vehicle endpoints
    # -----------------------------------------------------------------

    def get_vehicle_endpoints(self) -> list[dict[str, Any]]:
        """
        Find the latest observation for every vehicle.

        These are possible starting points for missing-trajectory
        recovery.

        Only observations belonging to actual vehicles are considered.
        """

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        v.id AS vehicle_id,
                        vo.id AS observation_id,
                        vo.camera_id,
                        c.code AS camera_code,
                        vo.ts,
                        vo.plate_text
                    FROM vehicles v
                    JOIN LATERAL (
                        SELECT *
                        FROM vehicle_observations vo
                        WHERE vo.vehicle_id = v.id
                        ORDER BY vo.ts DESC
                        LIMIT 1
                    ) vo ON TRUE
                    JOIN cameras c
                        ON c.id = vo.camera_id
                    ORDER BY vo.ts ASC
                    """
                )
            ).mappings().all()

        return [dict(row) for row in rows]

    # -----------------------------------------------------------------
    # Candidate target vehicles
    # -----------------------------------------------------------------

    def find_candidate_targets(
        self,
        source: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Find vehicles whose first observation occurs shortly after
        the source vehicle's last observation.

        Candidates already directly reachable from the source camera
        are excluded because Part 3 should have handled direct links.
        """

        source_vehicle_id = source["vehicle_id"]
        source_camera_id = int(source["camera_id"])
        source_ts = source["ts"]

        # Make sure the timestamp is datetime-like.
        if not isinstance(source_ts, datetime):
            raise TypeError(
                f"source['ts'] must be datetime, got {type(source_ts)}"
            )

        max_ts = source_ts + timedelta(seconds=MAX_GAP_S)

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT
                        v.id AS vehicle_id,
                        vo.id AS observation_id,
                        vo.camera_id,
                        c.code AS camera_code,
                        vo.ts,
                        vo.plate_text
                    FROM vehicles v
                    JOIN LATERAL (
                        SELECT *
                        FROM vehicle_observations vo
                        WHERE vo.vehicle_id = v.id
                        ORDER BY vo.ts ASC
                        LIMIT 1
                    ) vo ON TRUE
                    JOIN cameras c
                        ON c.id = vo.camera_id
                    WHERE v.id <> :source_vehicle_id
                      AND vo.ts > :source_ts
                      AND vo.ts <= :max_ts
                    ORDER BY vo.ts ASC
                    """
                ),
                {
                    "source_vehicle_id": str(source_vehicle_id),
                    "source_ts": source_ts,
                    "max_ts": max_ts,
                },
            ).mappings().all()

        # Direct neighbors are already handled by Part 3.
        reachable = set(
            self.graph.successors(source_camera_id)
        )

        candidates: list[dict[str, Any]] = []

        for row in rows:
            target_camera_id = int(row["camera_id"])

            # Part 3 handles direct topology transitions.
            if target_camera_id in reachable:
                continue

            gap_s = (
                row["ts"] - source_ts
            ).total_seconds()

            if gap_s <= 0 or gap_s > MAX_GAP_S:
                continue

            item = dict(row)
            item["gap_s"] = float(gap_s)

            candidates.append(item)

        return candidates

    # -----------------------------------------------------------------
    # Re-ID
    # -----------------------------------------------------------------

    def _get_reid_vector(
        self,
        observation_id: UUID,
    ) -> Optional[list[float]]:
        """
        Read a stored Re-ID vector.

        Returns None when no embedding exists.
        """

        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT vector
                    FROM reid_embeddings
                    WHERE observation_id = :observation_id
                    LIMIT 1
                    """
                ),
                {
                    "observation_id": str(observation_id),
                },
            ).first()

        if row is None:
            return None

        value = row[0]

        if value is None:
            return None

        try:
            return [float(x) for x in value]
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _cosine_similarity(
        a: Optional[list[float]],
        b: Optional[list[float]],
    ) -> Optional[float]:
        if not a or not b:
            return None

        if len(a) != len(b):
            return None

        dot = sum(x * y for x, y in zip(a, b))

        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return None

        cosine = dot / (norm_a * norm_b)

        # Map [-1, 1] -> [0, 1]
        return max(
            0.0,
            min(
                1.0,
                (cosine + 1.0) / 2.0,
            ),
        )

    # -----------------------------------------------------------------
    # Plate
    # -----------------------------------------------------------------

    @staticmethod
    def _plate_similarity(
        plate_a: Optional[str],
        plate_b: Optional[str],
    ) -> Optional[float]:
        if not plate_a or not plate_b:
            return None

        a = "".join(
            ch for ch in plate_a.upper()
            if ch.isalnum()
        )

        b = "".join(
            ch for ch in plate_b.upper()
            if ch.isalnum()
        )

        if not a or not b:
            return None

        if a == b:
            return 1.0

        # Simple normalized edit similarity.
        m = len(a)
        n = len(b)

        dp = list(range(n + 1))

        for i in range(1, m + 1):
            previous = dp[0]
            dp[0] = i

            for j in range(1, n + 1):
                current = dp[j]

                cost = (
                    0
                    if a[i - 1] == b[j - 1]
                    else 1
                )

                dp[j] = min(
                    dp[j] + 1,
                    dp[j - 1] + 1,
                    previous + cost,
                )

                previous = current

        distance = dp[n]
        max_len = max(m, n)

        return max(
            0.0,
            min(
                1.0,
                1.0 - (distance / max_len),
            ),
        )

    # -----------------------------------------------------------------
    # Path scoring
    # -----------------------------------------------------------------

    def _path_time(
        self,
        path: list[int],
    ) -> tuple[float, float, float]:
        """
        Returns:

        typical_total_s
        min_total_s
        max_total_s
        """

        typical = 0.0
        minimum = 0.0
        maximum = 0.0

        for from_node, to_node in zip(
            path,
            path[1:],
        ):
            edge = self.graph[from_node][to_node]

            typical += float(
                edge["typical_travel_s"]
            )

            minimum += float(
                edge["min_travel_s"]
            )

            maximum += float(
                edge["max_travel_s"]
            )

        return typical, minimum, maximum

    @staticmethod
    def _time_score(
        gap_s: float,
        minimum: float,
        maximum: float,
        typical: float,
    ) -> float:
        """
        Score how plausible the observed time gap is
        for the candidate path.
        """

        if gap_s < minimum or gap_s > maximum:
            return 0.0

        if typical <= 0:
            return 0.5

        deviation = abs(
            gap_s - typical
        ) / typical

        return max(
            0.0,
            min(
                1.0,
                1.0 - deviation,
            ),
        )

    def _path_popularity(
        self,
        path: list[int],
    ) -> Optional[float]:
        """
        Score based on historical edge frequency.

        If every edge has zero historical frequency,
        return None so the popularity signal is excluded
        and the remaining weights are renormalized.
        """

        frequencies: list[float] = []

        for from_node, to_node in zip(
            path,
            path[1:],
        ):
            edge = self.graph[from_node][to_node]

            frequencies.append(
                float(edge["historical_freq"])
            )

        if not frequencies:
            return None

        maximum = max(frequencies)

        # Honest cold-start handling:
        # all seeded frequencies are 0.
        if maximum <= 0:
            return None

        average = sum(frequencies) / len(
            frequencies
        )

        return min(
            1.0,
            average / maximum,
        )

    # -----------------------------------------------------------------
    # Fusion
    # -----------------------------------------------------------------

    @staticmethod
    def _combine_scores(
        scores: dict[str, Optional[float]],
    ) -> tuple[float, dict[str, float]]:
        """
        Drop missing signals and renormalize remaining weights.
        """

        available = {
            name: score
            for name, score in scores.items()
            if score is not None
        }

        if not available:
            return 0.0, {}

        raw_weights = {
            name: BASE_WEIGHTS[name]
            for name in available
        }

        total_weight = sum(
            raw_weights.values()
        )

        weights = {
            name: weight / total_weight
            for name, weight in raw_weights.items()
        }

        score = sum(
            available[name] * weights[name]
            for name in available
        )

        return (
            max(
                0.0,
                min(
                    1.0,
                    score,
                ),
            ),
            weights,
        )

    # -----------------------------------------------------------------
    # Evaluate candidate
    # -----------------------------------------------------------------

    def evaluate_candidate(
        self,
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> Optional[RecoveryResult]:
        source_camera = int(
            source["camera_id"]
        )

        target_camera = int(
            target["camera_id"]
        )

        if source_camera == target_camera:
            return None

        gap_s = float(
            target["gap_s"]
        )

        source_observation_id = (
            source["observation_id"]
        )

        target_observation_id = (
            target["observation_id"]
        )

        source_reid = self._get_reid_vector(
            source_observation_id
        )

        target_reid = self._get_reid_vector(
            target_observation_id
        )

        reid_score = self._cosine_similarity(
            source_reid,
            target_reid,
        )

        plate_score = self._plate_similarity(
            source.get("plate_text"),
            target.get("plate_text"),
        )

        best_path: Optional[list[int]] = None
        best_score = -1.0
        best_details: Optional[
            dict[str, Any]
        ] = None

        try:
            paths = nx.shortest_simple_paths(
                self.graph,
                source_camera,
                target_camera,
                weight="typical_travel_s",
            )
        except (
            nx.NetworkXNoPath,
            nx.NodeNotFound,
        ):
            return None

        for index, path in enumerate(paths):

            if index >= K_PATHS:
                break

            typical, minimum, maximum = (
                self._path_time(path)
            )

            time_score = self._time_score(
                gap_s,
                minimum,
                maximum,
                typical,
            )

            # If the path itself cannot fit the
            # observed time gap, don't consider it.
            if time_score <= 0:
                continue

            popularity_score = (
                self._path_popularity(path)
            )

            score, weights = (
                self._combine_scores(
                    {
                        "time": time_score,
                        "popularity": popularity_score,
                        "plate": plate_score,
                        "reid": reid_score,
                    }
                )
            )

            if score > best_score:
                best_score = score
                best_path = list(path)

                best_details = {
                    "gap_s": gap_s,
                    "typical_travel_s": typical,
                    "min_travel_s": minimum,
                    "max_travel_s": maximum,
                    "time_score": time_score,
                    "popularity_score": popularity_score,
                    "plate_score": plate_score,
                    "reid_score": reid_score,
                    "weights": weights,
                    "path_count_checked": index + 1,
                }

        if (
            best_path is None
            or best_details is None
        ):
            return None

        status = (
            "recovery_candidate"
            if best_score >= RECOVERY_THRESHOLD
            else "below_threshold"
        )

        return RecoveryResult(
            source_vehicle_id=source[
                "vehicle_id"
            ],
            target_vehicle_id=target[
                "vehicle_id"
            ],
            from_camera_id=source_camera,
            to_camera_id=target_camera,
            path_camera_ids=best_path,
            confidence=best_score,
            status=status,
            time_score=best_details[
                "time_score"
            ],
            popularity_score=best_details[
                "popularity_score"
            ],
            plate_score=best_details[
                "plate_score"
            ],
            reid_score=best_details[
                "reid_score"
            ],
            evidence=best_details,
        )

    # -----------------------------------------------------------------
    # Safe scan
    # -----------------------------------------------------------------

    def scan(self) -> list[RecoveryResult]:
        """
        Read-only recovery scan.

        IMPORTANT:
        This method does NOT write anything to the database.
        """

        endpoints = self.get_vehicle_endpoints()

        results: list[RecoveryResult] = []

        for source in endpoints:
            candidates = (
                self.find_candidate_targets(
                    source
                )
            )

            for target in candidates:
                result = (
                    self.evaluate_candidate(
                        source,
                        target,
                    )
                )

                if result is not None:
                    results.append(result)

        results.sort(
            key=lambda result: result.confidence,
            reverse=True,
        )

        return results

    # -----------------------------------------------------------------
    # DB writes - intentionally isolated
    # -----------------------------------------------------------------

    def write_inferred_segment(
        self,
        result: RecoveryResult,
    ) -> UUID:
        """
        Write one inferred trajectory segment.

        This is intentionally isolated from scan() so read-only
        testing never mutates the database.
        """

        segment_id = uuid.uuid4()

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
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
                    VALUES
                    (
                        :id,
                        :vehicle_id,
                        :from_camera_id,
                        :to_camera_id,
                        'inferred',
                        CAST(:path_camera_ids AS integer[]),
                        :confidence
                    )
                    """
                ),
                {
                    "id": str(segment_id),
                    "vehicle_id": str(
                        result.source_vehicle_id
                    ),
                    "from_camera_id": (
                        result.from_camera_id
                    ),
                    "to_camera_id": (
                        result.to_camera_id
                    ),
                    "path_camera_ids": (
                        "{" +
                        ",".join(
                            str(camera_id)
                            for camera_id
                            in result.path_camera_ids
                        )
                        + "}"
                    ),
                    "confidence": result.confidence,
                },
            )

        return segment_id

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def close(self) -> None:
        self.engine.dispose()


# ---------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------

def run_recovery_scan() -> list[RecoveryResult]:
    """
    Convenience wrapper for the read-only recovery scan.
    """

    engine = RecoveryEngine()

    try:
        return engine.scan()
    finally:
        engine.close()


__all__ = [
    "RECOVERY_THRESHOLD",
    "MAX_GAP_S",
    "K_PATHS",
    "RecoveryResult",
    "RecoveryEngine",
    "run_recovery_scan",
]