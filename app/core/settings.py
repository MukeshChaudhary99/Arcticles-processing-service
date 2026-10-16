from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/articles"
    )
    environment: Literal["development", "test", "production"] = "development"
    allow_dev_tenant_header: bool = False
    db_pool_size: int = Field(default=5, ge=1, le=100)
    db_max_overflow: int = Field(default=5, ge=0, le=100)
    db_pool_timeout: int = Field(default=10, ge=1)
    db_pool_recycle: int = Field(default=1800, ge=1)
    db_statement_timeout_ms: int = Field(default=15000, ge=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @model_validator(mode="after")
    def validate_configuration(self):
        if not self.database_url.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg://")
        if self.environment == "production":
            if self.allow_dev_tenant_header:
                raise ValueError(
                    "Development tenant headers are forbidden in production"
                )
            # Fail closed until an authenticated tenant resolver is installed.
            raise ValueError(
                "Configure authenticated tenant resolution before production deployment"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
