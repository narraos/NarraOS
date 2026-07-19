"""Environment-driven application settings.

Loads NARRAOS_*-prefixed environment variables (and a local .env file, if
present) into a single typed settings object.

This is intentionally minimal: infra-level settings only (environment name,
log level, database/cache connection strings, config directory). The full
Configuration System described in PROVIDER_ARCHITECTURE.md section 15
(layered providers.*.yaml, per-stage overrides, versioned Configuration_v1
snapshots) is Core Infrastructure work, not part of Day 0 repository
foundation. Nothing here should grow agent-, stage-, or provider-specific
fields; add those when Core Infrastructure builds the real Configuration
System on top of this.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Matches the environment names used by config/providers.<environment>.yaml."""

    LOCAL = "local"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Infra-level application settings, loaded from NARRAOS_*-prefixed env vars."""

    model_config = SettingsConfigDict(
        env_prefix="NARRAOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL
    log_level: str = Field(default="INFO")

    database_url: str = Field(
        default="postgresql+asyncpg://narraos:narraos@localhost:5432/narraos",
        description="PostgreSQL connection string for the Database Layer.",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string for the Layer 1 queue/cache.",
    )

    config_dir: Path = Field(
        default=Path("config"),
        description="Directory containing providers.*.yaml and plugins/*.yaml.",
    )


def get_settings() -> Settings:
    """Return a freshly loaded Settings instance.

    Deliberately not cached at import time -- tests and tooling frequently
    need to reload settings against a different environment without a
    process restart. Callers that want a single shared instance should
    construct one explicitly and pass it down, rather than relying on this
    function to act as a singleton.
    """
    return Settings()
