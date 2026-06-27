"""对标视频链接下载适配器（yt-dlp CLI）。"""

import subprocess
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings
from app.services.storage_service import task_dir, touch_file


class UrlDownloadAdapter:
    """通过 yt-dlp 将对标视频下载到任务 input 目录。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    def is_remote_url(self, value: str | None) -> bool:
        """判断路径是否为 http(s) URL。"""
        if not value:
            return False
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"}

    def download(self, task_id: str, url: str) -> str:
        """下载远程视频到本地 source.mp4。

        参数：
            task_id: 任务 ID。
            url: 对标视频链接。

        返回：
            本地 mp4 绝对路径。
        """
        if not self.settings.enable_url_import:
            raise ValueError("URL 导入未启用，请设置 ENABLE_URL_IMPORT=true")
        if not self.is_remote_url(url):
            raise ValueError("无效的视频链接，仅支持 http/https")

        output_path = task_dir(task_id) / "input" / "source.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.settings.use_stub_model_adapters:
            return touch_file(task_id, "input/source.mp4", b"stub downloaded video")

        template = str(output_path.with_suffix("")) + ".%(ext)s"
        command = [
            self.settings.url_download_command,
            "--no-playlist",
            "--merge-output-format",
            "mp4",
            "-f",
            "best[ext=mp4]/best",
            "-o",
            template,
            url.strip(),
        ]
        if self.settings.url_max_size_mb:
            command.extend(["--max-filesize", f"{self.settings.url_max_size_mb}M"])

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=self.settings.url_download_timeout_seconds,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "未知错误").strip()
            raise RuntimeError(f"视频下载失败: {detail}")

        if output_path.exists():
            return str(output_path)

        # yt-dlp 可能输出非 .mp4 后缀，取 input 目录下最新视频文件
        candidates = sorted(
            (p for p in output_path.parent.iterdir() if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".webm"}),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError("下载完成但未找到视频文件")
        downloaded = candidates[0]
        if downloaded != output_path:
            downloaded.rename(output_path)
        return str(output_path)


def resolve_local_video_path(task_id: str, source_path: str) -> str:
    """若 source_path 为 URL 则下载，否则原样返回本地路径。"""
    adapter = UrlDownloadAdapter()
    if adapter.is_remote_url(source_path):
        return adapter.download(task_id, source_path)
    if not Path(source_path).exists() and not source_path.startswith("/"):
        storage_path = get_settings().storage_root / source_path.replace("\\", "/")
        if storage_path.exists():
            return str(storage_path)
    return source_path
