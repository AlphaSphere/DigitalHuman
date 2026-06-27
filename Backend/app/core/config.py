"""
用途：集中管理应用运行时配置，从环境变量与 `.env` 读取数据库、模型服务、存储等连接信息。
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    用途：数字人后端全部可配置项的类型安全容器，贯穿任务流水线、模型适配与分发模块。
    """

    app_name: str = "Digital Human API"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # 本地桌面模式：SQLite + Celery 同步执行，无需 Docker / Redis / 独立 Worker
    local_desktop_mode: bool = False

    database_url: str = "mysql+pymysql://digital_human:digital_human@mysql:3306/digital_human"
    redis_url: str = "redis://redis:6379/0"
    storage_root: Path = Path("./storage")

    whisper_base_url: str | None = None
    whisper_command: str = "whisper"
    whisper_model: str = "base"
    whisper_language: str | None = "zh"
    whisper_device: str | None = None
    cozyvoice_base_url: str = "http://cozyvoice:8002"
    heygem_base_url: str = "http://heygem:8003"
    # 单段配音通常数秒；长视频会拆成多段请求，留足余量即可
    model_http_timeout_seconds: float = 600
    use_stub_model_adapters: bool = True

    ffmpeg_command: str = "ffmpeg"
    ffprobe_command: str = "ffprobe"

    music_library_path: Path = Path("./storage/music")
    enable_background_music: bool = True

    social_auto_upload_command: str = "sau"
    social_auto_upload_account: str = "default"
    social_auto_upload_workdir: Path | None = None
    social_auto_upload_timeout_seconds: float = 900
    enable_distribution: bool = False
    bilibili_default_tid: int = 249

    url_download_command: str = "yt-dlp"
    url_download_timeout_seconds: float = 600
    url_max_size_mb: int = 500
    enable_url_import: bool = True

    ffmpeg_font_path: Path | None = None

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: float = 120
    enable_llm_rewrite: bool = True

    enable_cover_generation: bool = True
    cover_default_template: str = "title_on_frame"

    playwright_chrome_cdp_url: str = "http://host.docker.internal:9222"
    playwright_publish_timeout_seconds: float = 900

    tuilionnx_base_url: str = "http://tuilionnx:8004"

    _project_root = Path(__file__).resolve().parents[3]

    model_config = SettingsConfigDict(
        env_file=str(_project_root / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator(
        "whisper_language",
        "whisper_device",
        "whisper_base_url",
        "social_auto_upload_workdir",
        "ffmpeg_font_path",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value):
        """
        用途：将环境变量中的空字符串规范为 None，避免可选配置被误判为有效值。

        参数：
            value: 原始字段值（字符串或其它类型）

        返回：
            None（当值为空字符串）或原值

        逻辑：
            1. 空字符串在 Docker/Compose 中常见，需与「未设置」语义对齐
        """
        return None if value == "" else value

    @property
    def cors_origin_list(self) -> list[str]:
        """
        用途：把逗号分隔的 CORS 源字符串解析为列表，供 CORSMiddleware 使用。

        返回：
            去空白后的允许来源 URL 列表
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """
    用途：单例获取应用配置，并在首次加载时确保存储目录存在。

    返回：
        已缓存的 Settings 实例

    逻辑：
        1. 使用 lru_cache 保证进程内只解析一次环境变量
        2. 创建 storage_root 与 music_library_path，避免后续写文件失败
    """
    settings = Settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    settings.music_library_path.mkdir(parents=True, exist_ok=True)
    return settings
