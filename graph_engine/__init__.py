"""
URBANTRACE Part 3 - Graph Engine
"""

from .fusion import (
    BASE_WEIGHTS,
    FusionResult,
    compute_fusion,
    cosine_similarity,
    plate_similarity,
    time_feasibility,
)

from .association import (
    AUTO_LINK_THRESHOLD,
    REVIEW_THRESHOLD,
    AssociationEngine,
    run_association,
)

from .movement_graph import MovementGraph


__all__ = [
    "BASE_WEIGHTS",
    "FusionResult",
    "compute_fusion",
    "cosine_similarity",
    "plate_similarity",
    "time_feasibility",
    "AUTO_LINK_THRESHOLD",
    "REVIEW_THRESHOLD",
    "AssociationEngine",
    "run_association",
    "MovementGraph",
]