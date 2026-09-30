"""
Application configuration for URBANTRACE backend.

Reads environment variables (see .env.example at repo root) and exposes a
singleton `settings` object, plus a helper to load the demo city YAML that
drives the digital twin (roads, cameras, topology, zones).
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "URBANTRACE API"
    environment: str = "development"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "urbantrace"
    postgres_user: str = "urbantrace"
    postgres_password: str = "urbantrace_dev_password"

    redis_host: str = "localhost"
    redis_port: int = 6379

    demo_city_config_path: str = "/configs/demo_city.yaml"

    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_demo_city() -> dict[str, Any]:
    """Load the synthetic demo city (zones/roads/cameras/topology) from YAML.

    Falls back to a local repo-relative path if the container path isn't
    present, so this also works when running the API outside Docker.
    """
    settings = get_settings()
    candidates = [
        Path(settings.demo_city_config_path),
        Path(__file__).resolve().parents[2] / "configs" / "demo_city.yaml",
    ]
    for path in candidates:
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f)
    raise FileNotFoundError(
        f"demo_city.yaml not found in any of: {[str(c) for c in candidates]}"
    )
