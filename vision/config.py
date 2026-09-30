"""Configuration for the URBANTRACE perception pipeline."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class VisionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VISION_",
        extra="ignore",
    )

    # YOLO
    yolo_model: str = "yolov8n.pt"
    yolo_conf_threshold: float = 0.35

    # COCO:
    # 2 = car
    # 3 = motorcycle
    # 5 = bus
    # 7 = truck
    yolo_classes: list[int] = [2, 3, 5, 7]

    # ByteTrack
    tracker_config: str = "bytetrack.yaml"

    # Process every Nth frame
    sample_every_n_frames: int = 3

    # Re-ID
    reid_model_version: str = "cv-baseline-v1"
    reid_vector_dim: int = 144

    # OCR
    ocr_enabled: bool = True

    # Crops
    crops_dir: Path = Path("data/crops")

    # Processing limits
    max_crop_width: int = 640
    max_crop_height: int = 640

    # Camera health reporting interval
    health_every_n_frames: int = 30


def get_vision_settings() -> VisionSettings:
    return VisionSettings()