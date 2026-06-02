from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Digital Human API"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = "mysql+pymysql://digital_human:digital_human@mysql:3306/digital_human"
    redis_url: str = "redis://redis:6379/0"
    storage_root: Path = Path("/app/storage")

    whisper_base_url: str = "http://whisper:8001"
    whisper_command: str = "whisper"
    whisper_model: str = "base"
    whisper_language: str | None = "zh"
    whisper_device: str | None = None
    cozyvoice_base_url: str = "http://cozyvoice:8002"
    heygem_base_url: str = "http://heygem:8003"
    model_http_timeout_seconds: float = 600
    use_stub_model_adapters: bool = True

    ffmpeg_command: str = "ffmpeg"
    ffprobe_command: str = "ffprobe"

    music_library_path: Path = Path("/app/storage/music")
    enable_background_music: bool = True

    social_auto_upload_command: str = "sau"
    social_auto_upload_account: str = "default"
    social_auto_upload_workdir: Path | None = None
    social_auto_upload_timeout_seconds: float = 900
    enable_distribution: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("whisper_language", "whisper_device", "social_auto_upload_workdir", mode="before")
    @classmethod
    def empty_string_to_none(cls, value):
        return None if value == "" else value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    settings.music_library_path.mkdir(parents=True, exist_ok=True)
    return settings
