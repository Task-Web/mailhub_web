import os
from functools import lru_cache
from typing import List

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    app_name: str = "Base Experiment Backend"
    api_prefix: str = "/api"
    cookie_name: str = "user_id"
    cookie_max_age: int = 60 * 60 * 24 * 30  # 30 days
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    debug: bool = False
    files_dir: str = "files"
    state_ttl_seconds: int = 12 * 60 * 60
    state_max_entries: int = 1000
    state_max_total_bytes: int = 1024 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    # lru_cache to reuse settings across requests
    return Settings(_env_file=os.getenv("ENV_FILE", ".env"))
