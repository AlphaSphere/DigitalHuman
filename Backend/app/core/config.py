from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Digital Human API"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = "mysql+pymysql://digital_human:digital_human@mysql:3306/digital_human"
    redis_url: str = "redis://redis:6379/0"
    storage_root: Path = Path("/app/storage")

    whisper_base_url: str = "http://whisper:8001"
    cozyvoice_base_url: str = "http://cozyvoice:8002"
    heygem_base_url: str = "http://heygem:8003"
    model_http_timeout_seconds: float = 600
    use_stub_model_adapters: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    return settings
