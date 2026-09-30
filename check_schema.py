import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from sqlalchemy import create_engine, text
from app.config import get_settings

engine = create_engine(get_settings().sync_database_url)

with engine.connect() as c:
    for table in [
        "vehicles",
        "camera_transitions",
        "review_queue",
        "camera_topology",
    ]:
        print(f"\n--- {table.upper()} ---")

        rows = c.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = :table
                ORDER BY ordinal_position
            """),
            {"table": table},
        ).fetchall()

        for row in rows:
            print(row)