"""Runtime configuration, read from environment variables (see the repo's .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED_DIR = API_ROOT / "data" / "seed"
INSECURE_DEV_SECRET = "dev-only-insecure-secret-change-me-please"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "marketmind"

    jwt_secret: SecretStr = SecretStr(INSECURE_DEV_SECRET)
    jwt_ttl_minutes: int = Field(default=60 * 24 * 3, ge=5, le=60 * 24 * 30)

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    cors_origin_regex: str | None = None

    seed_dir: Path = DEFAULT_SEED_DIR
    auto_seed: bool = True
    train_on_startup: bool = True

    demo_users_are_admin: bool = True
    demo_ttl_hours: int = Field(default=24, ge=1, le=24 * 30)
    # Global cap on new demo shoppers, so a flood of sign-ups can't fill a 512 MB Atlas M0.
    demo_global_limit_per_hour: int = Field(default=120, ge=1)

    retrain_cooldown_seconds: int = Field(default=120, ge=0)
    # Number of threads implicit may use; 1 keeps the free-tier box responsive while training.
    train_threads: int = Field(default=1, ge=0, le=64)

    auth_rate_limit_per_minute: int = Field(default=20, ge=1)
    events_rate_limit_per_minute: int = Field(default=120, ge=1)
    # Behind Render's proxy the real client IP is the right-most X-Forwarded-For entry.
    trust_forwarded_for: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> Settings:
        secret = self.jwt_secret.get_secret_value()
        if self.app_env == "production" and (secret == INSECURE_DEV_SECRET or len(secret) < 32):
            raise ValueError("JWT_SECRET must be set to a random value of at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
