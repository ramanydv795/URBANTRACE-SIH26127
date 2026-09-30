from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings


engine = create_engine(
    get_settings().sync_database_url,
    pool_pre_ping=True,
)


def generate_alerts() -> list[dict]:
    """
    Generate actionable alerts from real anomalies and bottlenecks.

    Existing alerts are not duplicated.
    """

    with engine.begin() as conn:
        anomalies = conn.execute(
            text(
                """
                SELECT
                    id,
                    type,
                    reason,
                    confidence,
                    vehicle_id,
                    journey_id
                FROM anomalies
                WHERE confidence >= 0.80
                ORDER BY detected_at DESC
                """
            )
        ).mappings().all()

        results = []

        for anomaly in anomalies:
            ref_id = str(anomaly["id"])

            existing = conn.execute(
                text(
                    """
                    SELECT id
                    FROM alerts
                    WHERE
                        ref_table = 'anomalies'
                        AND ref_id = :ref_id
                    LIMIT 1
                    """
                ),
                {"ref_id": ref_id},
            ).first()

            if existing:
                continue

            severity = (
                "high"
                if float(anomaly["confidence"]) >= 0.90
                else "medium"
            )

            message = (
                f"Traffic anomaly detected: "
                f"{anomaly['type']}. "
                f"{anomaly['reason']}"
            )

            conn.execute(
                text(
                    """
                    INSERT INTO alerts
                    (
                        category,
                        ref_table,
                        ref_id,
                        message,
                        severity,
                        status
                    )
                    VALUES
                    (
                        'traffic_anomaly',
                        'anomalies',
                        :ref_id,
                        :message,
                        :severity,
                        'open'
                    )
                    """
                ),
                {
                    "ref_id": ref_id,
                    "message": message,
                    "severity": severity,
                },
            )

            results.append(
                {
                    "ref_table": "anomalies",
                    "ref_id": ref_id,
                    "category": "traffic_anomaly",
                    "severity": severity,
                    "message": message,
                }
            )

        bottlenecks = conn.execute(
            text(
                """
                SELECT
                    id,
                    road_id,
                    severity,
                    explanation
                FROM bottlenecks
                WHERE severity IN ('high', 'medium')
                """
            )
        ).mappings().all()

        for bottleneck in bottlenecks:
            ref_id = str(bottleneck["id"])

            existing = conn.execute(
                text(
                    """
                    SELECT id
                    FROM alerts
                    WHERE
                        ref_table = 'bottlenecks'
                        AND ref_id = :ref_id
                    LIMIT 1
                    """
                ),
                {"ref_id": ref_id},
            ).first()

            if existing:
                continue

            message = (
                f"Bottleneck detected on road "
                f"{bottleneck['road_id']}. "
                f"{bottleneck['explanation']}"
            )

            conn.execute(
                text(
                    """
                    INSERT INTO alerts
                    (
                        category,
                        ref_table,
                        ref_id,
                        message,
                        severity,
                        status
                    )
                    VALUES
                    (
                        'bottleneck',
                        'bottlenecks',
                        :ref_id,
                        :message,
                        :severity,
                        'open'
                    )
                    """
                ),
                {
                    "ref_id": ref_id,
                    "message": message,
                    "severity": bottleneck["severity"],
                },
            )

            results.append(
                {
                    "ref_table": "bottlenecks",
                    "ref_id": ref_id,
                    "category": "bottleneck",
                    "severity": bottleneck["severity"],
                    "message": message,
                }
            )

        return results
