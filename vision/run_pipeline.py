"""
CLI entry point for the URBANTRACE Part 2 perception pipeline.

Examples:

    python -m vision.run_pipeline \
        --camera C01 \
        --source data/videos/c01.mp4

Windows PowerShell:

    python -m vision.run_pipeline --camera C01 --source data/videos/c01.mp4

Webcam:

    python -m vision.run_pipeline --camera C01 --source 0
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from vision.config import get_vision_settings
from vision.pipeline import PerceptionPipeline


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "URBANTRACE Part 2 "
            "vehicle perception pipeline"
        )
    )

    parser.add_argument(
        "--camera",
        required=True,
        help="Camera code, e.g. C01",
    )

    parser.add_argument(
        "--source",
        required=True,
        help=(
            "Video file path, RTSP URL, "
            "or webcam index such as 0"
        ),
    )

    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional maximum number of frames to read",
    )

    parser.add_argument(
        "--sample-every",
        type=int,
        default=None,
        help="Override frame sampling interval",
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=[
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
        ],
    )

    return parser.parse_args()


def main() -> int:

    args = parse_args()

    logging.basicConfig(
        level=getattr(
            logging,
            args.log_level,
        ),
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
    )

    settings = get_vision_settings()

    if args.sample_every is not None:

        if args.sample_every < 1:
            print(
                "--sample-every must be >= 1",
                file=sys.stderr,
            )

            return 2

        settings.sample_every_n_frames = (
            args.sample_every
        )

    # Convert numeric webcam source to integer.
    source: str | int = args.source

    if args.source.isdigit():
        source = int(args.source)

    pipeline = None

    try:

        pipeline = PerceptionPipeline(
            settings
        )

        print()
        print(
            "========================================"
        )
        print(
            " URBANTRACE — PART 2 PERCEPTION"
        )
        print(
            "========================================"
        )
        print(
            f"Camera: {args.camera}"
        )
        print(
            f"Source: {args.source}"
        )
        print(
            f"YOLO available: "
            f"{pipeline.detector.available}"
        )
        print(
            f"OCR available: "
            f"{pipeline.plate_reader.available}"
        )
        print(
            f"Re-ID available: "
            f"{pipeline.reid.available}"
        )
        print(
            "========================================"
        )
        print()

        summary = pipeline.process_video(
            source=source,
            camera_code=args.camera,
            max_frames=args.max_frames,
        )

        print(
            json.dumps(
                summary,
                indent=2,
            )
        )

        return 0

    except KeyboardInterrupt:

        print(
            "\nPipeline stopped by user."
        )

        return 130

    except Exception as exc:

        logging.getLogger(
            "vision.run_pipeline"
        ).exception(
            "Pipeline failed: %s",
            exc,
        )

        return 1

    finally:

        if pipeline is not None:
            pipeline.close()


if __name__ == "__main__":
    raise SystemExit(
        main()
    )