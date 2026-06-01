import subprocess

from app.core.config import get_settings
from app.services.storage_service import touch_file, write_text


class FFmpegAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_subtitle(self, task_id: str, script: str) -> str:
        return write_text(task_id, "intermediate/subtitle.srt", self._to_srt(script))

    def compose_final(self, task_id: str, base_video_path: str, audio_path: str, subtitle_path: str) -> str:
        output_path = self.settings.storage_root / "tasks" / task_id / "output" / "final_with_subtitle.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.settings.use_stub_model_adapters:
            return touch_file(task_id, "output/final_with_subtitle.mp4", b"stub final video")
        # 真实环境要求 Worker 镜像安装 ffmpeg；失败会抛出异常并由 Celery 写入任务错误状态。
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                base_video_path,
                "-i",
                audio_path,
                "-vf",
                f"subtitles={subtitle_path}",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(output_path),
            ],
            check=True,
        )
        return str(output_path)

    def _to_srt(self, script: str) -> str:
        lines = [line.strip() for line in script.splitlines() if line.strip()]
        if not lines:
            lines = [script.strip()]
        blocks = []
        for index, line in enumerate(lines, start=1):
            start = (index - 1) * 4
            end = start + 4
            blocks.append(f"{index}\n00:00:{start:02d},000 --> 00:00:{end:02d},000\n{line}\n")
        return "\n".join(blocks)
