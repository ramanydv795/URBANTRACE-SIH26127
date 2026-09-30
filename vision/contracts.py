"""Data contracts between perception stages."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BBox:
    x: float
    y: float
    w: float
    h: float

    def as_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
        }


@dataclass
class VehicleObservationResult:
    camera_code: str
    ts: datetime
    track_id: int | None

    bbox: BBox

    detection_conf: float

    vehicle_type: str | None = None
    type_conf: float | None = None

    color: str | None = None
    color_conf: float | None = None

    plate_text: str | None = None
    plate_conf: float | None = None

    reid_vector: list[float] | None = None
    reid_model_version: str | None = None

    frame_ref: str | None = None

    warnings: list[str] = field(
        default_factory=list
    )