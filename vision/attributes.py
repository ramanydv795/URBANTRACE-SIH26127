"""
Vehicle attribute extraction.

Vehicle type comes from YOLO.

Vehicle color uses a lightweight HSV + k-means baseline.
"""

from __future__ import annotations

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


_NAMED_COLORS_HSV = {
    "white": (0, 0, 235),
    "black": (0, 0, 25),
    "gray": (0, 0, 130),
    "silver": (0, 0, 190),
    "red": (0, 200, 180),
    "blue": (110, 200, 180),
    "green": (60, 180, 150),
    "yellow": (28, 200, 200),
    "orange": (14, 210, 210),
}


def _nearest_color_name(
    h: float,
    s: float,
    v: float,
) -> str:

    if s < 30 and v > 200:
        return "white"

    if v < 45:
        return "black"

    if s < 40:
        return "gray" if v < 170 else "silver"

    best_name = "gray"
    best_dist = float("inf")

    for name, (
        rh,
        rs,
        rv,
    ) in _NAMED_COLORS_HSV.items():

        if name in {
            "white",
            "black",
            "gray",
            "silver",
        }:
            continue

        hue_distance = min(
            abs(h - rh),
            180 - abs(h - rh),
        )

        distance = (
            hue_distance * 2
            + abs(s - rs) * 0.3
            + abs(v - rv) * 0.1
        )

        if distance < best_dist:
            best_dist = distance
            best_name = name

    return best_name


def extract_color(
    bgr_crop: np.ndarray,
) -> tuple[str | None, float]:

    if (
        cv2 is None
        or bgr_crop is None
        or bgr_crop.size == 0
    ):
        return None, 0.0

    height, width = bgr_crop.shape[:2]

    if height < 6 or width < 6:
        return None, 0.0

    y0 = int(height * 0.25)
    y1 = int(height * 0.75)

    x0 = int(width * 0.20)
    x1 = int(width * 0.80)

    region = bgr_crop[
        y0:y1,
        x0:x1,
    ]

    if region.size == 0:
        region = bgr_crop

    hsv = cv2.cvtColor(
        region,
        cv2.COLOR_BGR2HSV,
    )

    hsv = hsv.reshape(
        -1,
        3,
    ).astype(np.float32)

    k = 3

    if hsv.shape[0] < k:
        return None, 0.0

    criteria = (
        cv2.TERM_CRITERIA_EPS
        + cv2.TERM_CRITERIA_MAX_ITER,
        10,
        1.0,
    )

    _, labels, centers = cv2.kmeans(
        hsv,
        k,
        None,
        criteria,
        3,
        cv2.KMEANS_PP_CENTERS,
    )

    counts = np.bincount(
        labels.flatten(),
        minlength=k,
    )

    dominant_idx = int(
        np.argmax(counts)
    )

    confidence = (
        float(counts[dominant_idx])
        / float(len(labels))
    )

    h, s, v = centers[dominant_idx]

    color_name = _nearest_color_name(
        float(h),
        float(s),
        float(v),
    )

    return color_name, round(
        confidence,
        3,
    )


def resolve_type(
    cls_name: str,
    detection_conf: float,
) -> tuple[str, float]:

    return (
        cls_name,
        round(
            detection_conf,
            3,
        ),
    )