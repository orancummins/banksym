"""Application settings, sourced from the environment (prefix ``BANKSYM_``)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    ``database_url`` defaults to a local SQLite file so the framework persists state out of the box
    with zero infrastructure; point ``BANKSYM_DATABASE_URL`` at PostgreSQL for a shared deployment.
    """

    model_config = SettingsConfigDict(env_prefix="BANKSYM_", extra="ignore")

    database_url: str = "sqlite:///banksym.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
