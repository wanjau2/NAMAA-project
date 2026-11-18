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
    # Extraction / SSE (D004)
    extraction_timeout_ms: int = 90_000
    extraction_heartbeat_ms: int = 5_000
    extraction_worker_poll_ms: int = 500
    extraction_mode: str = "offline_fixture"  # offline_fixture | medgemma (gated)
    # Outbox / FHIR saga (D004)
    outbox_worker_poll_ms: int = 1_000
    outbox_max_attempts: int = 5
    outbox_lease_seconds: int = 30
    outbox_backoff_base_seconds: int = 1
    fhir_gateway_mode: str = "stub"  # stub | hapi (gated)
    fhir_inject_failure_rate: float = 0.0  # test hook: 0..1

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()