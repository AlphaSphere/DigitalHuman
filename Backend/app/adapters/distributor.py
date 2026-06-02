"""多平台视频分发适配器（CLI）。"""

import subprocess

from app.core.config import get_settings


class DistributorAdapter:
    """social-auto-upload（sau）CLI 适配器。

    外部服务：social-auto-upload 开源项目，通过命令行向 B 站等平台上传视频。
    本适配器不直接调用平台 API，而是封装 subprocess 调用 sau，便于复用其登录态与上传逻辑。

    接入方式：
    - **CLI**：唯一生产路径，需配置 `social_auto_upload_command`、账号与工作目录。
    - 功能开关：`enable_distribution=false` 时直接返回失败说明，不执行命令。
    - 无 Stub：分发依赖真实账号 Cookie，开发环境通常关闭 ENABLE_DISTRIBUTION。
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def upload_video(self, platform: str, file_path: str, title: str, description: str, tags: list[str]) -> dict:
        """将成片视频上传到指定社交平台。

        用途：
            Celery 分发任务调用，把最终 mp4 发布到 B 站等平台并记录外链。

        参数：
            platform: 平台标识（如 `bilibili`），传给 sau 子命令。
            file_path: 本地视频文件绝对路径。
            title: 发布标题。
            description: 发布简介/描述。
            tags: 标签列表，CLI 侧以逗号拼接。

        返回：
            字典，含 `status`（success/failed）、`external_url`（成功时）、
            `error_message`（失败时）、`raw`（原始 stdout/命令等调试信息）。

        逻辑：
            1. 若未启用分发，返回 failed 及配置提示。
            2. 组装 sau 命令：平台、upload-video、账号、文件、标题、描述。
            3. B 站额外附加固定分区 tid=249。
            4. 若有 tags，追加 `--tags` 参数。
            5. subprocess 执行，捕获 stdout/stderr；超时或 returncode≠0 则 failed。
            6. 成功时从 stdout 解析首个 http(s) URL 作为 external_url。
        """
        if not self.settings.enable_distribution:
            return {
                "status": "failed",
                "error_message": "分发功能未启用，请配置 ENABLE_DISTRIBUTION=true 并安装 social-auto-upload sau CLI。",
            }
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
            command.extend(["--tid", "249"])
        if tags:
            command.extend(["--tags", ",".join(tags)])
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
        """从 CLI 标准输出中解析发布后的视频链接。

        用途：
            sau 成功上传后可能在 stdout 打印 URL，供写入 DistributionRecord。

        参数：
            output: subprocess 的 stdout 文本。

        返回：
            第一个 http/https URL，若无则 None。
        """
        for token in output.split():
            if token.startswith("http://") or token.startswith("https://"):
                return token
        return None
