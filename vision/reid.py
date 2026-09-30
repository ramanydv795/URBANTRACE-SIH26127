"""
Classical-CV vehicle Re-ID baseline.

Embedding:
    128-bin HSV histogram
    +
    16-bin gradient orientation histogram

Total:
    144 dimensions

This is deliberately labelled cv-baseline-v1 and should not be confused
with a learned OSNet/ResNet vehicle Re-ID model.
"""

from __future__ import annotations

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from vision.config import VisionSettings


_COLOR_BINS = 128
_GRADIENT_BINS = 16


def _color_histogram(
    bgr_crop: np.ndarray,
) -> np.ndarray:

    hsv = cv2.cvtColor(
        bgr_crop,
        cv2.COLOR_BGR2HSV,
    )

    hist = cv2.calcHist(
        [hsv],
        [0, 1],
        None,
        [16, 8],
        [0, 180, 0, 256],
    )

    hist = cv2.normalize(
        hist,
        hist,
    )

    return hist.flatten()


def _gradient_orientation_histogram(
    bgr_crop: np.ndarray,
) -> np.ndarray:

    gray = cv2.cvtColor(
        bgr_crop,
        cv2.COLOR_BGR2GRAY,
    )

    gx = cv2.Sobel(
        gray,
        cv2.CV_32F,
        1,
        0,
        ksize=3,
    )

    gy = cv2.Sobel(
        gray,
        cv2.CV_32F,
        0,
        1,
        ksize=3,
    )

    magnitude, angle = cv2.cartToPolar(
        gx,
        gy,
        angleInDegrees=True,
    )

    hist, _ = np.histogram(
        angle,
        bins=_GRADIENT_BINS,
        range=(0, 360),
        weights=magnitude,
    )

    norm = np.linalg.norm(hist)

    if norm > 0:
        return hist / norm

    return hist


class ReIDEmbedder:

    def __init__(
        self,
        settings: VisionSettings,
    ):
        self.settings = settings

        self.available = cv2 is not None

        self.model_version = (
            settings.reid_model_version
        )

    def embed(
        self,
        bgr_crop: np.ndarray,
    ) -> list[float] | None:

        if (
            not self.available
            or bgr_crop is None
            or bgr_crop.size == 0
        ):
            return None

        height, width = bgr_crop.shape[:2]

        if height < 8 or width < 8:
            return None

        resized = cv2.resize(
            bgr_crop,
            (128, 128),
        )

        color_vec = _color_histogram(
            resized
        )

        gradient_vec = (
            _gradient_orientation_histogram(
                resized
            )
        )

        vector = np.concatenate(
            [
                color_vec,
                gradient_vec,
            ]
        ).astype(np.float32)

        norm = np.linalg.norm(vector)

        if norm > 0:
            vector = vector / norm

        return vector.tolist()


def cosine_similarity(
    a: list[float],
    b: list[float],
) -> float:

    va = np.array(
        a,
        dtype=np.float32,
    )

    vb = np.array(
        b,
        dtype=np.float32,
    )

    denominator = (
        np.linalg.norm(va)
        * np.linalg.norm(vb)
    )

    if denominator == 0:
        return 0.0

    return float(
        np.dot(va, vb)
        / denominator
    )