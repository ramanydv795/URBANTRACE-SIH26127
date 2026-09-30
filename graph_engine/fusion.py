"""
URBANTRACE Part 3 - Fusion Scorer

Pure scoring logic for cross-camera vehicle association.

No database access.
No global state.
No identity assignment.

Given:
    - departure observation
    - arrival observation
    - topology/travel constraints

Returns:
    FusionResult containing:
        - final confidence
        - individual signal scores
        - signals actually used
        - missing signals
        - effective weights
        - human-readable evidence
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from math import sqrt
from typing import Any, Mapping, Sequence


# ---------------------------------------------------------------------------
# Base weights
# ---------------------------------------------------------------------------

BASE_WEIGHTS = {
    "plate": 0.35,
    "reid": 0.35,
    "time": 0.15,
    "direction": 0.10,
    "topology": 0.05,
}


# ---------------------------------------------------------------------------
# Result contract
# ---------------------------------------------------------------------------

@dataclass
class FusionResult:
    score: float

    plate_similarity: float | None
    reid_similarity: float | None
    time_feasibility: float | None
    direction_compatibility: float | None
    topology_reachability: float | None

    signals_used: list[str]
    missing_signals: list[str]
    weights_used: dict[str, float]

    time_delta_seconds: float | None
    expected_min_seconds: float | None
    expected_max_seconds: float | None

    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _normalise_plate(value: str | None) -> str:
    if not value:
        return ""

    return "".join(
        character.upper()
        for character in str(value)
        if character.isalnum()
    )


# Common OCR confusions.
OCR_EQUIVALENTS = {
    "0": {"O", "0"},
    "O": {"O", "0"},
    "1": {"I", "1"},
    "I": {"I", "1"},
    "8": {"B", "8"},
    "B": {"B", "8"},
    "5": {"S", "5"},
    "S": {"S", "5"},
}


def _ocr_aware_substitution_cost(a: str, b: str) -> float:
    if a == b:
        return 0.0

    if b in OCR_EQUIVALENTS.get(a, set()):
        return 0.25

    return 1.0


# ---------------------------------------------------------------------------
# Plate similarity
# ---------------------------------------------------------------------------

def plate_similarity(
    plate_a: str | None,
    plate_b: str | None,
) -> float | None:
    """
    OCR-aware normalized edit similarity.

    Returns:
        0..1 when both plates exist.
        None when either plate is unavailable.
    """

    a = _normalise_plate(plate_a)
    b = _normalise_plate(plate_b)

    if not a or not b:
        return None

    rows = len(a) + 1
    cols = len(b) + 1

    dp = [[0.0] * cols for _ in range(rows)]

    for i in range(rows):
        dp[i][0] = float(i)

    for j in range(cols):
        dp[0][j] = float(j)

    for i in range(1, rows):
        for j in range(1, cols):
            substitution = (
                dp[i - 1][j - 1]
                + _ocr_aware_substitution_cost(a[i - 1], b[j - 1])
            )

            insertion = dp[i][j - 1] + 1.0
            deletion = dp[i - 1][j] + 1.0

            dp[i][j] = min(
                substitution,
                insertion,
                deletion,
            )

    distance = dp[-1][-1]
    normalizer = max(len(a), len(b), 1)

    return _clamp(1.0 - (distance / normalizer))


# ---------------------------------------------------------------------------
# Re-ID similarity
# ---------------------------------------------------------------------------

def cosine_similarity(
    vector_a: Sequence[float] | None,
    vector_b: Sequence[float] | None,
) -> float | None:
    """
    Cosine similarity converted from [-1, 1] into [0, 1].

    This keeps the FusionResult easy to interpret.
    """

    if vector_a is None or vector_b is None:
        return None

    if len(vector_a) == 0 or len(vector_b) == 0:
        return None

    if len(vector_a) != len(vector_b):
        return None

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for a, b in zip(vector_a, vector_b):
        af = float(a)
        bf = float(b)

        dot += af * bf
        norm_a += af * af
        norm_b += bf * bf

    denominator = sqrt(norm_a) * sqrt(norm_b)

    if denominator == 0.0:
        return None

    cosine = dot / denominator

    # Convert [-1, 1] -> [0, 1].
    return _clamp((cosine + 1.0) / 2.0)


# ---------------------------------------------------------------------------
# Time feasibility
# ---------------------------------------------------------------------------

def _seconds_between(
    departure: datetime,
    arrival: datetime,
) -> float:
    return (arrival - departure).total_seconds()


def time_feasibility(
    departure_ts: datetime,
    arrival_ts: datetime,
    min_travel_s: float | None,
    max_travel_s: float | None,
) -> tuple[float | None, float | None]:
    """
    Score whether observed travel time is physically plausible.

    Returns:
        (score, observed_delta_seconds)

    Score:
        1.0  = comfortably inside the allowed range
        0.0  = outside the allowed range

    If topology doesn't provide bounds, the signal is unavailable.
    """

    if min_travel_s is None and max_travel_s is None:
        return None, None

    delta = _seconds_between(departure_ts, arrival_ts)

    if delta < 0:
        return 0.0, delta

    minimum = (
        float(min_travel_s)
        if min_travel_s is not None
        else 0.0
    )

    maximum = (
        float(max_travel_s)
        if max_travel_s is not None
        else float("inf")
    )

    if delta < minimum:
        # Too fast.
        if minimum <= 0:
            return 0.0, delta

        distance = minimum - delta

        # Graceful decay rather than a hard jump.
        score = 1.0 - min(distance / minimum, 1.0)

        return _clamp(score), delta

    if delta > maximum:
        # Too slow.
        if maximum == float("inf"):
            return 1.0, delta

        distance = delta - maximum

        score = 1.0 - min(
            distance / max(maximum, 1.0),
            1.0,
        )

        return _clamp(score), delta

    # Inside valid range.
    if maximum == float("inf"):
        return 1.0, delta

    # Highest confidence around the middle of the allowed window.
    midpoint = (minimum + maximum) / 2.0
    half_range = max((maximum - minimum) / 2.0, 1.0)

    distance_from_midpoint = abs(delta - midpoint)

    score = 1.0 - (
        distance_from_midpoint / half_range
    ) * 0.25

    return _clamp(score), delta


# ---------------------------------------------------------------------------
# Main fusion function
# ---------------------------------------------------------------------------

def compute_fusion(
    departure: Mapping[str, Any],
    arrival: Mapping[str, Any],
    *,
    reid_vector_departure: Sequence[float] | None = None,
    reid_vector_arrival: Sequence[float] | None = None,
    min_travel_s: float | None = None,
    max_travel_s: float | None = None,
    topology_exists: bool = True,
) -> FusionResult:
    """
    Compute an explainable cross-camera match score.

    `departure` and `arrival` are deliberately generic mappings so this
    module does not depend on SQLAlchemy models.

    Expected keys:

        ts
        plate_text
        camera_code (optional, used only in evidence)

    Re-ID vectors are supplied separately because they normally come
    from the reid_embeddings table.
    """

    # ---------------------------------------------------------------
    # Plate
    # ---------------------------------------------------------------

    plate_score = plate_similarity(
        departure.get("plate_text"),
        arrival.get("plate_text"),
    )

    # ---------------------------------------------------------------
    # Re-ID
    # ---------------------------------------------------------------

    reid_score = cosine_similarity(
        reid_vector_departure,
        reid_vector_arrival,
    )

    # ---------------------------------------------------------------
    # Time
    # ---------------------------------------------------------------

    departure_ts = departure.get("ts")
    arrival_ts = arrival.get("ts")

    time_score: float | None = None
    delta_seconds: float | None = None

    if (
        isinstance(departure_ts, datetime)
        and isinstance(arrival_ts, datetime)
    ):
        time_score, delta_seconds = time_feasibility(
            departure_ts,
            arrival_ts,
            min_travel_s,
            max_travel_s,
        )

    # ---------------------------------------------------------------
    # Topology
    # ---------------------------------------------------------------

    topology_score: float | None = (
        1.0 if topology_exists else 0.0
    )

    # ---------------------------------------------------------------
    # Direction
    #
    # IMPORTANT:
    # Part 2 doesn't provide vehicle heading.
    #
    # Therefore we do NOT pretend to know actual direction.
    # Current implementation uses topology edge existence as the
    # direction-compatible signal.
    # ---------------------------------------------------------------

    direction_score: float | None = (
        1.0 if topology_exists else 0.0
    )

    # ---------------------------------------------------------------
    # Collect available signals
    # ---------------------------------------------------------------

    raw_scores = {
        "plate": plate_score,
        "reid": reid_score,
        "time": time_score,
        "direction": direction_score,
        "topology": topology_score,
    }

    signals_used = [
        name
        for name, value in raw_scores.items()
        if value is not None
    ]

    missing_signals = [
        name
        for name, value in raw_scores.items()
        if value is None
    ]

    # ---------------------------------------------------------------
    # Weight renormalization
    #
    # Missing signals are removed completely.
    # Their weight is NOT treated as zero.
    # ---------------------------------------------------------------

    total_weight = sum(
        BASE_WEIGHTS[name]
        for name in signals_used
    )

    if total_weight <= 0:
        weights_used = {}
        final_score = 0.0
    else:
        weights_used = {
            name: BASE_WEIGHTS[name] / total_weight
            for name in signals_used
        }

        final_score = sum(
            raw_scores[name] * weights_used[name]
            for name in signals_used
        )

    final_score = _clamp(final_score)

    # ---------------------------------------------------------------
    # Explainable evidence
    # ---------------------------------------------------------------

    evidence = {
        "score": final_score,

        "plate": {
            "available": plate_score is not None,
            "similarity": plate_score,
        },

        "reid": {
            "available": reid_score is not None,
            "similarity": reid_score,
        },

        "time": {
            "available": time_score is not None,
            "feasibility": time_score,
            "observed_seconds": delta_seconds,
            "expected_min_seconds": min_travel_s,
            "expected_max_seconds": max_travel_s,
        },

        "direction": {
            "available": direction_score is not None,
            "score": direction_score,
            "method": "topology_edge_existence",
            "limitation": (
                "Part 2 does not provide per-vehicle heading; "
                "this is topology compatibility, not actual heading."
            ),
        },

        "topology": {
            "available": topology_score is not None,
            "reachable": topology_exists,
            "score": topology_score,
        },

        "signals_used": signals_used,
        "missing_signals": missing_signals,
        "weights_used": weights_used,

        "departure_camera": departure.get("camera_code"),
        "arrival_camera": arrival.get("camera_code"),
    }

    return FusionResult(
        score=final_score,

        plate_similarity=plate_score,
        reid_similarity=reid_score,
        time_feasibility=time_score,
        direction_compatibility=direction_score,
        topology_reachability=topology_score,

        signals_used=signals_used,
        missing_signals=missing_signals,
        weights_used=weights_used,

        time_delta_seconds=delta_seconds,
        expected_min_seconds=min_travel_s,
        expected_max_seconds=max_travel_s,

        evidence=evidence,
    )


__all__ = [
    "BASE_WEIGHTS",
    "FusionResult",
    "plate_similarity",
    "cosine_similarity",
    "time_feasibility",
    "compute_fusion",
]