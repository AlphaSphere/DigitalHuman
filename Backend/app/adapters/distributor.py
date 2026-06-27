"""多平台视频分发适配器（CLI + Playwright）。"""

import subprocess

from app.adapters.playwright_publisher import PlaywrightPublisher
from app.core.config import get_settings


class DistributorAdapter:
    """social-auto-upload（sau）CLI 与 Playwright 发布适配器。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.playwright = PlaywrightPublisher()

    def upload_video(
        self,
        platform: str,
        file_path: str,
        title: str,
        description: str,
        tags: list[str],
        cover_path: str | None = None,
        attach_cover: bool = False,
    ) -> dict:
        """将成片视频上传到指定社交平台。"""
        if not self.settings.enable_distribution:
            return {
                "status": "failed",
                "error_message": "分发功能未启用，请配置 ENABLE_DISTRIBUTION=true 并安装 social-auto-upload sau CLI。",
            }

        if platform in PlaywrightPublisher.PLAYWRIGHT_PLATFORMS:
            return self.playwright.upload_video(
                platform, file_path, title, description, tags, cover_path, attach_cover
            )

        command = [
            self.settings.social_auto_upload_command,
            platform,
            "upload-video",
            "--account",
            self.settings.social_auto_upload_account,
            "--file",
            file_path,
            "--title",
            title,
            "--desc",
            description,
        ]
        if platform == "bilibili":
            command.extend(["--tid", str(self.settings.bilibili_default_tid)])
        if tags:
            command.extend(["--tags", ",".join(tags)])
        if cover_path and attach_cover:
            command.extend(["--cover", cover_path])
        try:
            result = subprocess.run(
                command,
                cwd=str(self.settings.social_auto_upload_workdir) if self.settings.social_auto_upload_workdir else None,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.settings.social_auto_upload_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return {"status": "failed", "error_message": f"分发超时: {exc}", "raw": {"command": command}}
        if result.returncode != 0:
            return {"status": "failed", "error_message": result.stderr or result.stdout, "raw": {"command": command}}
        return {
            "status": "success",
            "external_url": self._extract_url(result.stdout),
            "raw": {"stdout": result.stdout, "tags": tags},
        }

    def _extract_url(self, output: str) -> str | None:
        for token in output.split():
            if token.startswith("http://") or token.startswith("https://"):
                return token
        return None
