"""
URBANTRACE Part 2 perception pipeline.

Pipeline:

    video frame
        |
        v
    YOLO
        |
        v
    ByteTrack
        |
        +----> vehicle type
        |
        +----> color
        |
        +----> ANPR
        |
        +----> Re-ID embedding
        |
        v
    VehicleObservationResult
        |
        v
    PostgreSQL

This module deliberately does NOT perform cross-camera identity fusion.
That belongs to Part 3.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from vision.anpr import PlateReader
from vision.attributes import extract_color, resolve_type
from vision.config import VisionSettings
from vision.contracts import (
    BBox,
    VehicleObservationResult,
)
from vision.db_writer import PerceptionDBWriter
from vision.detector import DetectorTracker
from vision.reid import ReIDEmbedder

logger = logging.getLogger("vision.pipeline")


class PerceptionPipeline:

    def __init__(
        self,
        settings: VisionSettings | None = None,
        db_writer: PerceptionDBWriter | None = None,
    ):

        self.settings = (
            settings
            or VisionSettings()
        )

        self.detector = DetectorTracker(
            self.settings
        )

        self.plate_reader = PlateReader(
            self.settings
        )
        self._plate_cache = {}
        self._plate_last_ocr_frame = {}
        self._ocr_interval_frames = 30

        self.reid = ReIDEmbedder(
            self.settings
        )

        self.db = (
            db_writer
            or PerceptionDBWriter()
        )

        self.settings.crops_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.camera_id_cache: dict[str, int] = {}

    def camera_id(
        self,
        camera_code: str,
    ) -> int:

        if camera_code not in self.camera_id_cache:

            self.camera_id_cache[
                camera_code
            ] = self.db.get_camera_id(
                camera_code
            )

        return self.camera_id_cache[
            camera_code
        ]

    @staticmethod
    def _clip_box(
        box,
        frame_width: int,
        frame_height: int,
    ) -> tuple[int, int, int, int]:

        x1 = max(
            0,
            int(box.x),
        )

        y1 = max(
            0,
            int(box.y),
        )

        x2 = min(
            frame_width,
            int(box.x + box.w),
        )

        y2 = min(
            frame_height,
            int(box.y + box.h),
        )

        return x1, y1, x2, y2

    def _save_crop(
        self,
        crop: np.ndarray,
        camera_code: str,
        frame_number: int,
        track_id: int | None,
    ) -> str | None:

        if (
            crop is None
            or crop.size == 0
        ):
            return None

        camera_dir = (
            self.settings.crops_dir
            / camera_code
        )

        camera_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        track_name = (
            str(track_id)
            if track_id is not None
            else "untracked"
        )

        filename = (
            f"frame_{frame_number:08d}"
            f"_track_{track_name}.jpg"
        )

        path = camera_dir / filename

        success = cv2.imwrite(
            str(path),
            crop,
        )

        if not success:
            return None

        return str(path)

    def process_frame(
        self,
        frame: np.ndarray,
        camera_code: str,
        frame_number: int,
        timestamp: datetime | None = None,
    ) -> list[VehicleObservationResult]:

        timestamp = (
            timestamp
            or datetime.now(timezone.utc)
        )

        if (
            frame is None
            or frame.size == 0
        ):
            return []

        detections = (
            self.detector.process_frame(
                frame
            )
        )

        if not detections:
            return []

        frame_height, frame_width = (
            frame.shape[:2]
        )

        results: list[
            VehicleObservationResult
        ] = []

        for detection in detections:

            x1, y1, x2, y2 = (
                self._clip_box(
                    detection,
                    frame_width,
                    frame_height,
                )
            )

            if x2 <= x1 or y2 <= y1:
                continue

            crop = frame[
                y1:y2,
                x1:x2,
            ]

            if crop.size == 0:
                continue

            warnings: list[str] = []

            # --------------------------------------------------
            # Vehicle type
            # --------------------------------------------------
            vehicle_type, type_conf = (
                resolve_type(
                    detection.cls_name,
                    detection.detection_conf,
                )
            )

            # --------------------------------------------------
            # Color
            # --------------------------------------------------
            color, color_conf = (
                extract_color(crop)
            )

            if color is None:
                warnings.append(
                    "color_unavailable"
                )

            # --------------------------------------------------
            # ANPR
            # --------------------------------------------------
            # PaddleOCR is expensive. Run it periodically per tracked
            # vehicle and reuse the latest result between OCR passes.
            # This preserves ANPR in the pipeline without OCR'ing the
            # same vehicle on every sampled frame.
            track_id = detection.track_id
            cached_plate = (
                self._plate_cache.get(track_id)
                if track_id is not None
                else None
            )
            last_ocr_frame = (
                self._plate_last_ocr_frame.get(
                    track_id,
                    -10**9,
                )
                if track_id is not None
                else -10**9
            )

            should_run_ocr = (
                track_id is None
                or cached_plate is None
                or frame_number - last_ocr_frame
                >= self._ocr_interval_frames
            )

            if should_run_ocr:
                plate_text, plate_conf = (
                    self.plate_reader.read_plate(
                        crop
                    )
                )

                if track_id is not None:
                    self._plate_cache[track_id] = (
                        plate_text,
                        plate_conf,
                    )
                    self._plate_last_ocr_frame[
                        track_id
                    ] = frame_number
            else:
                plate_text, plate_conf = cached_plate

            if plate_text is None:
                warnings.append(
                    "plate_unavailable"
                )

            # --------------------------------------------------
            # Re-ID
            # --------------------------------------------------
            reid_vector = self.reid.embed(
                crop
            )

            if reid_vector is None:
                warnings.append(
                    "reid_unavailable"
                )

            # --------------------------------------------------
            # Crop persistence
            # --------------------------------------------------
            frame_ref = self._save_crop(
                crop,
                camera_code,
                frame_number,
                detection.track_id,
            )

            result = VehicleObservationResult(
                camera_code=camera_code,
                ts=timestamp,
                track_id=detection.track_id,
                bbox=BBox(
                    x=float(x1),
                    y=float(y1),
                    w=float(x2 - x1),
                    h=float(y2 - y1),
                ),
                detection_conf=detection.detection_conf,
                vehicle_type=vehicle_type,
                type_conf=type_conf,
                color=color,
                color_conf=color_conf,
                plate_text=plate_text,
                plate_conf=plate_conf,
                reid_vector=reid_vector,
                reid_model_version=(
                    self.reid.model_version
                    if reid_vector is not None
                    else None
                ),
                frame_ref=frame_ref,
                warnings=warnings,
            )

            results.append(result)

        return results

    def process_video(
        self,
        source: str | int,
        camera_code: str,
        max_frames: int | None = None,
    ) -> dict:

        camera_id = self.camera_id(
            camera_code
        )

        capture = cv2.VideoCapture(
            source
        )

        if not capture.isOpened():
            self.db.set_camera_status(
                camera_code,
                "offline",
            )

            raise RuntimeError(
                f"Unable to open video source: "
                f"{source}"
            )

        self.db.set_camera_status(
            camera_code,
            "online",
        )

        frame_number = 0
        processed_frames = 0
        observation_count = 0
        plate_successes = 0

        started_at = time.perf_counter()

        last_health_time = (
            time.perf_counter()
        )

        try:

            while True:

                success, frame = (
                    capture.read()
                )

                if not success:
                    break

                frame_number += 1

                # Sample every Nth frame.
                if (
                    frame_number
                    % self.settings.sample_every_n_frames
                    != 0
                ):
                    continue

                frame_start = (
                    time.perf_counter()
                )

                observations = (
                    self.process_frame(
                        frame,
                        camera_code,
                        frame_number,
                    )
                )

                for observation in observations:

                    self.db.write_observation(
                        observation,
                        camera_id,
                    )

                    observation_count += 1

                    if observation.plate_text:
                        plate_successes += 1

                processed_frames += 1

                # --------------------------------------------------
                # Camera health
                # --------------------------------------------------
                if (
                    frame_number
                    % self.settings.health_every_n_frames
                    == 0
                ):

                    elapsed = (
                        time.perf_counter()
                        - started_at
                    )

                    processing_fps = (
                        processed_frames
                        / elapsed
                        if elapsed > 0
                        else 0.0
                    )

                    latency_ms = (
                        (
                            time.perf_counter()
                            - frame_start
                        )
                        * 1000.0
                    )

                    ocr_rate = (
                        plate_successes
                        / observation_count
                        if observation_count > 0
                        else 0.0
                    )

                    self.db.write_health_metric(
                        camera_id=camera_id,
                        camera_code=camera_code,
                        fps=processing_fps,
                        processing_latency_ms=latency_ms,
                        detection_count=observation_count,
                        ocr_success_rate=ocr_rate,
                        stream_health="healthy",
                    )

                if (
                    max_frames is not None
                    and frame_number
                    >= max_frames
                ):
                    break

        finally:

            capture.release()

            self.db.set_camera_status(
                camera_code,
                "offline",
            )

        total_elapsed = (
            time.perf_counter()
            - started_at
        )

        return {
            "camera_code": camera_code,
            "source": str(source),
            "frames_read": frame_number,
            "frames_processed": processed_frames,
            "observations_written": observation_count,
            "plate_successes": plate_successes,
            "processing_seconds": round(
                total_elapsed,
                3,
            ),
            "detector_available": (
                self.detector.available
            ),
            "ocr_available": (
                self.plate_reader.available
            ),
            "reid_available": (
                self.reid.available
            ),
        }

    def close(self) -> None:
        self.db.close()