"""URBANTRACE Automatic Number Plate Recognition."""

from __future__ import annotations

import logging
import re

import cv2
import numpy as np

from vision.config import VisionSettings

logger = logging.getLogger("vision.anpr")

_CLEAN = re.compile(r"[^A-Z0-9]")


class PlateReader:
    def __init__(self, settings: VisionSettings):
        self.settings = settings
        self.available = False
        self._ocr = None
        self._easyocr = None
        self._load_error = None

        if settings.ocr_enabled:
            self._load()

    def _load(self):
        # -----------------------------------------------------
        # PaddleOCR - primary engine
        # -----------------------------------------------------
        try:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(lang="en")
            logger.info("PaddleOCR loaded successfully.")

        except Exception as exc:
            self._load_error = exc
            logger.warning(
                "PaddleOCR unavailable: %s",
                exc,
            )

        # -----------------------------------------------------
        # EasyOCR - fallback only
        # -----------------------------------------------------
        if self._ocr is None:
            try:
                import easyocr

                self._easyocr = easyocr.Reader(
                    ["en"],
                    gpu=False,
                    verbose=False,
                )

                logger.info("EasyOCR loaded successfully.")

            except Exception as exc:
                logger.warning(
                    "EasyOCR unavailable: %s",
                    exc,
                )

        self.available = (
            self._ocr is not None
            or self._easyocr is not None
        )

    # =========================================================
    # Candidate generation
    # =========================================================

    def _candidate_regions(
        self,
        vehicle: np.ndarray,
    ) -> list[np.ndarray]:

        if vehicle is None or vehicle.size == 0:
            return []

        h, w = vehicle.shape[:2]

        if h < 30 or w < 30:
            return []

        return [
            # First try the ORIGINAL vehicle crop.
            vehicle,

            # Then try the lower portion.
            vehicle[int(h * 0.30):h, :],
        ]

    # =========================================================
    # Preprocessing
    # =========================================================

    @staticmethod
    def _prepare(
        crop: np.ndarray,
    ) -> list[np.ndarray]:

        if crop is None or crop.size == 0:
            return []

        h, w = crop.shape[:2]

        scale = max(
            4.0,
            300.0 / max(w, 1),
        )

        scale = min(scale, 8.0)

        resized = cv2.resize(
            crop,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )

        gray = cv2.cvtColor(
            resized,
            cv2.COLOR_BGR2GRAY,
        )

        clahe = cv2.createCLAHE(
            clipLimit=3.0,
            tileGridSize=(8, 8),
        )

        enhanced = clahe.apply(gray)

        blurred = cv2.GaussianBlur(
            enhanced,
            (0, 0),
            1.0,
        )

        sharp = cv2.addWeighted(
            enhanced,
            1.8,
            blurred,
            -0.8,
            0,
        )

        return [
            resized,

            cv2.cvtColor(
                enhanced,
                cv2.COLOR_GRAY2BGR,
            ),

            cv2.cvtColor(
                sharp,
                cv2.COLOR_GRAY2BGR,
            ),
        ]

    # =========================================================
    # PaddleOCR parser
    # =========================================================

    @staticmethod
    def _parse_paddle(result):

        if not result:
            return None, 0.0

        best_text = None
        best_conf = 0.0

        try:
            for res in result:

                data = getattr(
                    res,
                    "json",
                    None,
                )

                if callable(data):
                    data = data()

                if not data:
                    continue

                if isinstance(data, dict):
                    data = data.get(
                        "res",
                        data,
                    )

                texts = data.get(
                    "rec_texts",
                    [],
                )

                scores = data.get(
                    "rec_scores",
                    [],
                )

                for raw_text, raw_score in zip(
                    texts,
                    scores,
                ):

                    text = _CLEAN.sub(
                        "",
                        str(raw_text).upper(),
                    )

                    try:
                        score = float(raw_score)
                    except Exception:
                        continue

                    if 4 <= len(text) <= 15:

                        if score > best_conf:
                            best_text = text
                            best_conf = score

        except Exception as exc:
            logger.debug(
                "PaddleOCR parsing failed: %s",
                exc,
            )

        return best_text, best_conf

    # =========================================================
    # EasyOCR parser
    # =========================================================

    @staticmethod
    def _parse_easyocr(results):

        best_text = None
        best_conf = 0.0

        for item in results:

            if len(item) < 3:
                continue

            raw_text = item[1]
            raw_conf = item[2]

            text = _CLEAN.sub(
                "",
                str(raw_text).upper(),
            )

            try:
                confidence = float(raw_conf)
            except Exception:
                continue

            if 4 <= len(text) <= 15:

                has_letter = any(
                    c.isalpha()
                    for c in text
                )

                has_digit = any(
                    c.isdigit()
                    for c in text
                )

                if has_letter and has_digit:
                    confidence += 0.05

                if confidence > best_conf:
                    best_text = text
                    best_conf = confidence

        return (
            best_text,
            min(round(best_conf, 3), 1.0),
        )

    # =========================================================
    # OCR one candidate
    # =========================================================

    def _ocr_candidate(
        self,
        crop: np.ndarray,
    ):

        best_text = None
        best_conf = 0.0

        prepared_images = self._prepare(crop)

        # -----------------------------------------------------
        # PaddleOCR
        # -----------------------------------------------------
        if self._ocr is not None:

            for image in prepared_images:

                try:
                    result = self._ocr.predict(
                        image
                    )

                    text, confidence = (
                        self._parse_paddle(result)
                    )

                    if confidence > best_conf:
                        best_text = text
                        best_conf = confidence

                    # Strong result -> stop immediately.
                    if (
                        best_text is not None
                        and best_conf >= 0.80
                    ):
                        return (
                            best_text,
                            best_conf,
                        )

                except Exception as exc:
                    logger.debug(
                        "PaddleOCR failed: %s",
                        exc,
                    )

            return (
                best_text,
                best_conf,
            )

        # -----------------------------------------------------
        # EasyOCR fallback
        # -----------------------------------------------------
        if self._easyocr is not None:

            for image in prepared_images:

                try:
                    result = self._easyocr.readtext(
                        image,
                        detail=1,
                        paragraph=False,
                        allowlist=(
                            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                            "0123456789"
                        ),
                    )

                    text, confidence = (
                        self._parse_easyocr(result)
                    )

                    if confidence > best_conf:
                        best_text = text
                        best_conf = confidence

                    if (
                        best_text is not None
                        and best_conf >= 0.80
                    ):
                        return (
                            best_text,
                            best_conf,
                        )

                except Exception as exc:
                    logger.debug(
                        "EasyOCR failed: %s",
                        exc,
                    )

        return (
            best_text,
            best_conf,
        )

    # =========================================================
    # Public API
    # =========================================================

    def read_plate(
        self,
        bgr_crop: np.ndarray,
    ) -> tuple[str | None, float]:

        if (
            not self.available
            or bgr_crop is None
            or bgr_crop.size == 0
        ):
            return None, 0.0

        candidates = self._candidate_regions(
            bgr_crop
        )

        best_text = None
        best_conf = 0.0

        for candidate in candidates:

            text, confidence = (
                self._ocr_candidate(candidate)
            )

            if text is None:
                continue

            if confidence > best_conf:
                best_text = text
                best_conf = confidence

            # Strong plate found.
            if best_conf >= 0.80:
                break

        return (
            best_text,
            round(best_conf, 3),
        )