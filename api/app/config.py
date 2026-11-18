from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NAMAA_",
        extra="ignore",
    )

    database_url: str = "sqlite:///./namaa_demo.sqlite3"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    demo_now: str = "2026-11-17T09:00:00Z"
    small_cell_threshold: int = 10

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()