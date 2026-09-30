"""
YOLO detection + ByteTrack intra-camera tracking.

Important:
ByteTrack IDs are local to a camera/video stream. They are NOT global
vehicle identities. Cross-camera identity belongs to Part 3.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from vision.config import VisionSettings

logger = logging.getLogger("vision.detector")

_COCO_VEHICLE_NAMES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


@dataclass
class TrackedBox:
    track_id: int | None

    x: float
    y: float
    w: float
    h: float

    cls_name: str

    detection_conf: float


class DetectorTracker:

    def __init__(
        self,
        settings: VisionSettings,
    ):
        self.settings = settings

        self.available = False
        self._model = None
        self._load_error: str | None = None

        self._load()

    def _load(self) -> None:
        try:
            from ultralytics import YOLO

            self._model = YOLO(self.settings.yolo_model)
            self._model.to("cuda:0")

            self.available = True

            logger.info(
                "YOLO loaded successfully: %s",
                self.settings.yolo_model,
            )

        except Exception as exc:
            self._load_error = str(exc)

            logger.warning(
                "YOLO unavailable: %s",
                exc,
            )

    def process_frame(
        self,
        frame: np.ndarray,
    ) -> list[TrackedBox]:

        if (
            not self.available
            or self._model is None
        ):
            return []

        try:
            results = self._model.track(
                frame,
                persist=True,
                tracker=self.settings.tracker_config,
                classes=self.settings.yolo_classes,
                conf=self.settings.yolo_conf_threshold,
                verbose=False,
            )
        except Exception as exc:
            logger.exception(
                "YOLO inference failed: %s",
                exc,
            )
            return []

        boxes: list[TrackedBox] = []

        if not results:
            return boxes

        result = results[0]

        if result.boxes is None:
            return boxes

        for box in result.boxes:

            cls_id = (
                int(box.cls[0])
                if box.cls is not None
                else None
            )

            cls_name = _COCO_VEHICLE_NAMES.get(
                cls_id,
                "vehicle",
            )

            confidence = (
                float(box.conf[0])
                if box.conf is not None
                else 0.0
            )

            track_id = (
                int(box.id[0])
                if box.id is not None
                else None
            )

            xyxy = box.xyxy[0].tolist()

            x1, y1, x2, y2 = xyxy

            boxes.append(
                TrackedBox(
                    track_id=track_id,
                    x=float(x1),
                    y=float(y1),
                    w=float(x2 - x1),
                    h=float(y2 - y1),
                    cls_name=cls_name,
                    detection_conf=confidence,
                )
            )

        return boxes