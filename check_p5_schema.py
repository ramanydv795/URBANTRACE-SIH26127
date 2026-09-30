import sys
sys.path.insert(0, "backend")

from sqlalchemy import create_engine, text
from app.config import get_settings

engine = create_engine(get_settings().sync_database_url)

tables = [
    "traffic_events",
]

with engine.connect() as conn:
    for table in tables:
        print(f"\n=== {table} ===")

        rows = conn.execute(
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