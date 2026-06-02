import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.services.storage_service import touch_file, write_text


class FFmpegAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def extract_audio(self, task_id: str, source_video_path: str) -> str:
        audio_path = self.settings.storage_root / "tasks" / task_id / "intermediate" / "source_audio.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        if self.settings.use_stub_model_adapters:
            return touch_file(task_id, "intermediate/source_audio.wav", b"stub source audio")
        subprocess.run(
            [
                self.settings.ffmpeg_command,
                "-y",
                "-i",
                source_video_path,
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(audio_path),
            ],
            check=True,
        )
        return str(audio_path)

    def generate_subtitle(self, task_id: str, script: str, segments: list | None = None) -> str:
        return write_text(task_id, "intermediate/subtitle.srt", self._to_srt(script, segments))

    def compose_final(
        self,
        task_id: str,
        base_video_path: str,
        audio_path: str,
        subtitle_path: str,
        background_music_path: str | None = None,
        background_music_volume: float | None = None,
    ) -> str:
        output_path = self.settings.storage_root / "tasks" / task_id / "output" / "final_with_subtitle.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.settings.use_stub_model_adapters:
            return touch_file(task_id, "output/final_with_subtitle.mp4", b"stub final video")
        if self.settings.enable_background_music and background_music_path and not Path(background_music_path).exists():
            raise ValueError(f"背景音乐文件不存在: {background_music_path}")
        # 真实环境要求 Worker 镜像安装 ffmpeg；失败会抛出异常并由 Celery 写入任务错误状态。
        command = [
            self.settings.ffmpeg_command,
            "-y",
            "-i",
            base_video_path,
            "-i",
            audio_path,
        ]
        if self.settings.enable_background_music and background_music_path:
            volume = background_music_volume if background_music_volume is not None else 0.18
            command.extend(
                [
                    "-stream_loop",
                    "-1",
                    "-i",
                    background_music_path,
                    "-filter_complex",
                    (
                        f"[2:a]volume={volume},afade=t=in:ss=0:d=2[music];"
                        "[1:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
                    ),
                    "-map",
                    "0:v",
                    "-map",
                    "[aout]",
                ]
            )
        else:
            command.extend(["-map", "0:v", "-map", "1:a"])
        command.extend(
            [
                "-vf",
                f"subtitles={self._escape_filter_path(subtitle_path)}",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                "-shortest",
                str(output_path),
            ]
        )
        subprocess.run(
            command,
            check=True,
        )
        return str(output_path)

    def _to_srt(self, script: str, segments: list | None = None) -> str:
        if segments:
            blocks = []
            for index, segment in enumerate(segments, start=1):
                text = getattr(segment, "edited_text", None) or getattr(segment, "original_text", "")
                start_time = getattr(segment, "start_time", None) or (index - 1) * 4
                end_time = getattr(segment, "end_time", None) or start_time + 4
                blocks.append(f"{index}\n{self._srt_time(start_time)} --> {self._srt_time(end_time)}\n{text}\n")
            return "\n".join(blocks)
        lines = [line.strip() for line in script.splitlines() if line.strip()]
        if not lines:
            lines = [script.strip()]
        blocks = []
        for index, line in enumerate(lines, start=1):
            start = (index - 1) * 4
            end = start + 4
            blocks.append(f"{index}\n{self._srt_time(start)} --> {self._srt_time(end)}\n{line}\n")
        return "\n".join(blocks)

    def _srt_time(self, seconds: float) -> str:
        millis = int((seconds - int(seconds)) * 1000)
        total = int(seconds)
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _escape_filter_path(self, path: str) -> str:
        # FFmpeg subtitles filter 会把冒号等字符当作参数分隔符，需要单独转义路径。
        return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
