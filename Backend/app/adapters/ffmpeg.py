"""FFmpeg 音视频处理适配器（CLI / Stub）。"""

import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.services.storage_service import touch_file, write_text


class FFmpegAdapter:
    """FFmpeg 命令行适配器。

    外部工具：系统安装的 ffmpeg/ffprobe，负责抽轨、字幕烧录、混音与编码。
    Worker 镜像需预装 ffmpeg；Stub 模式下跳过实际转码。

    接入方式：
    - **CLI**：生产环境唯一路径，通过 subprocess 调用配置的 ffmpeg_command。
    - **Stub**：`use_stub_model_adapters=true` 时对 extract_audio / compose_final 写占位文件。
    - generate_subtitle 纯 Python 生成 SRT，不调用 ffmpeg。
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def extract_audio(self, task_id: str, source_video_path: str) -> str:
        """从源视频中提取单声道 16kHz PCM 音频。

        用途：
            转写流水线第一步，为 Whisper ASR 准备 wav（Whisper 对 16k 单声道兼容性好）。

        参数：
            task_id: 任务 ID。
            source_video_path: 用户上传的源视频路径。

        返回：
            提取后的 wav 绝对路径（`intermediate/source_audio.wav`）。

        逻辑：
            1. 确保输出目录存在。
            2. Stub：写入占位 wav 并返回。
            3. ffmpeg -vn 去视频轨，pcm_s16le、16kHz、单声道输出。
        """
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
        """生成 SRT 字幕文件（不调用 FFmpeg）。

        用途：
            合成阶段将字幕烧录进成片；优先使用带时间戳的 ScriptSegment。

        参数：
            task_id: 任务 ID。
            script: 完整脚本文本（segments 为空时按行均分时间）。
            segments: 可选，ScriptSegmentModel 列表，含 start_time/end_time/edited_text。

        返回：
            写入的 `intermediate/subtitle.srt` 路径。
        """
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
        """合成带字幕（及可选背景音乐）的最终 mp4。

        用途：
            生成流水线最后一步：口播视频 + TTS 音轨 + 字幕 (+ BGM) → 成片。

        参数：
            task_id: 任务 ID。
            base_video_path: HeyGem 或用户上传的基础视频。
            audio_path: TTS 配音 wav。
            subtitle_path: SRT 字幕路径。
            background_music_path: 可选背景音乐文件。
            background_music_volume: BGM 音量系数，默认 0.18。

        返回：
            `output/final_with_subtitle.mp4` 绝对路径。

        逻辑：
            1. Stub：写入占位 mp4。
            2. 若启用 BGM 但文件不存在，抛出 ValueError。
            3. 构建 ffmpeg 命令：两路输入（视频、配音）；可选第三路 BGM。
            4. 有 BGM：filter_complex 做音量、淡入与 amix 混音。
            5. 无 BGM：直接 map 视频轨与配音轨。
            6. subtitles 滤镜烧录字幕，libx264 + aac，faststart，-shortest 截断至最短流。
            7. subprocess 执行，失败由 Celery 捕获并标记任务失败。
        """
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
        """将脚本或分段模型转为 SRT 文本。

        用途：
            内部方法，供 generate_subtitle 使用。

        参数：
            script:  fallback 全文，按行每 4 秒一条字幕。
            segments: 优先使用，从对象属性读取时间与文案。

        返回：
            符合 SRT 格式的字符串。
        """
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
        """将秒数格式化为 SRT 时间戳 `HH:MM:SS,mmm`。

        参数：
            seconds: 浮点秒数。

        返回：
            SRT 标准时间字符串。
        """
        millis = int((seconds - int(seconds)) * 1000)
        total = int(seconds)
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _escape_filter_path(self, path: str) -> str:
        """转义字幕文件路径，避免 ffmpeg subtitles 滤镜解析错误。

        用途：
            FFmpeg subtitles filter 会把冒号等字符当作参数分隔符，需要单独转义路径。

        参数：
            path: 原始文件路径。

        返回：
            可用于 -vf subtitles= 的路径字符串。
        """
        # FFmpeg subtitles filter 会把冒号等字符当作参数分隔符，需要单独转义路径。
        return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
