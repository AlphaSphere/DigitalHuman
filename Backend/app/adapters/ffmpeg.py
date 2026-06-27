"""FFmpeg 音视频处理适配器（CLI / Stub）。"""

import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.services.storage_service import touch_file, write_text

# 成片字幕默认样式（与配置页 DEFAULT_SUBTITLE_STYLE 保持一致）
_DEFAULT_SUBTITLE_STYLE: dict = {
    "enabled": True,
    "font_size": 20,
    "position": "bottom",
    "color": "#FFFFFF",
    "stroke": True,
    "font_family": "SimHei",
}

_OUTPUT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}


class FFmpegAdapter:
    """FFmpeg 命令行适配器。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    def extract_audio(self, task_id: str, source_video_path: str) -> str:
        """从源视频中提取单声道 16kHz PCM 音频。"""
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
        """生成 SRT 字幕文件（不调用 FFmpeg）。"""
        return write_text(task_id, "intermediate/subtitle.srt", self._to_srt(script, segments))

    def compose_final(
        self,
        task_id: str,
        base_video_path: str,
        audio_path: str,
        subtitle_path: str,
        background_music_path: str | None = None,
        background_music_volume: float | None = None,
        subtitle_style: dict | None = None,
        aspect_ratio: str | None = None,
        ai_watermark_enabled: bool = False,
        export_without_subtitle: bool = False,
    ) -> str:
        """合成带字幕（及可选背景音乐）的最终 mp4。"""
        output_path = self.settings.storage_root / "tasks" / task_id / "output" / "final_with_subtitle.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.settings.use_stub_model_adapters:
            touch_file(task_id, "output/final_with_subtitle.mp4", b"stub final video")
            if export_without_subtitle:
                touch_file(task_id, "output/final_no_subtitle.mp4", b"stub final video no subtitle")
            return str(output_path)
        if self.settings.enable_background_music and background_music_path and not Path(background_music_path).exists():
            raise ValueError(f"背景音乐文件不存在: {background_music_path}")

        no_subtitle_path = None
        if export_without_subtitle:
            no_subtitle_path = self.settings.storage_root / "tasks" / task_id / "output" / "final_no_subtitle.mp4"
            self._run_compose(
                base_video_path,
                audio_path,
                background_music_path,
                background_music_volume,
                None,
                aspect_ratio,
                ai_watermark_enabled,
                str(no_subtitle_path),
            )

        self._run_compose(
            base_video_path,
            audio_path,
            background_music_path,
            background_music_volume,
            subtitle_path,
            aspect_ratio,
            ai_watermark_enabled,
            str(output_path),
            subtitle_style,
        )
        return str(output_path)

    def _run_compose(
        self,
        base_video_path: str,
        audio_path: str,
        background_music_path: str | None,
        background_music_volume: float | None,
        subtitle_path: str | None,
        aspect_ratio: str | None,
        ai_watermark_enabled: bool,
        output_path: str,
        subtitle_style: dict | None = None,
    ) -> None:
        """执行单次 ffmpeg 合成命令。"""
        command = [self.settings.ffmpeg_command, "-y", "-i", base_video_path, "-i", audio_path]
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

        vf = self._build_video_filter(subtitle_path, subtitle_style, aspect_ratio, ai_watermark_enabled)
        if vf:
            command.extend(["-vf", vf])
        command.extend(
            [
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                "-shortest",
                output_path,
            ]
        )
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            tail = stderr[-2000:] if stderr else ""
            detail = tail or str(exc)
            raise RuntimeError(f"ffmpeg 合成失败（exit {exc.returncode}）: {detail}") from exc

    def _build_video_filter(
        self,
        subtitle_path: str | None,
        subtitle_style: dict | None,
        aspect_ratio: str | None,
        ai_watermark_enabled: bool,
    ) -> str:
        """构建 -vf 滤镜链。"""
        filters: list[str] = []
        if aspect_ratio:
            filters.append(self._scale_crop_filter(aspect_ratio))
        if subtitle_path and self._normalize_subtitle_style(subtitle_style).get("enabled", True):
            filters.append(self._build_subtitle_filter(subtitle_path, subtitle_style, aspect_ratio))
        if ai_watermark_enabled:
            filters.append(
                "drawtext=text='AI生成':fontcolor=white@0.6:fontsize=24:"
                "x=w-tw-20:y=h-th-20:box=1:boxcolor=black@0.4:boxborderw=8"
            )
        return ",".join(filters)

    def _scale_crop_filter(self, aspect_ratio: str) -> str:
        """按画幅比例裁剪缩放。"""
        mapping = {
            "9:16": "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "16:9": "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
            "1:1": "scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080",
        }
        return mapping.get(aspect_ratio, mapping["9:16"])

    def _output_dimensions(self, aspect_ratio: str | None) -> tuple[int, int]:
        """成片目标分辨率（与 scale/crop 一致，供 libass 正确换算字号与边距）。"""
        return _OUTPUT_DIMENSIONS.get(aspect_ratio or "9:16", _OUTPUT_DIMENSIONS["9:16"])

    def _normalize_subtitle_style(self, subtitle_style: dict | None) -> dict:
        """合并默认字幕样式，避免旧任务缺字段导致字号/位置异常。"""
        return {**_DEFAULT_SUBTITLE_STYLE, **(subtitle_style or {})}

    def _build_subtitle_filter(
        self,
        subtitle_path: str,
        subtitle_style: dict | None,
        aspect_ratio: str | None = None,
    ) -> str:
        """构建带样式的 subtitles 滤镜。

        libass 必须指定 original_size，否则 FontSize/MarginV 会按错误分辨率缩放，
        导致字幕偏大且无法贴底。
        """
        style = self._normalize_subtitle_style(subtitle_style)
        if not style.get("enabled", True):
            return ""
        if not Path(subtitle_path).exists():
            raise ValueError(f"字幕文件不存在: {subtitle_path}")
        width, height = self._output_dimensions(aspect_ratio)
        position = style.get("position", "bottom")
        font_size = int(style.get("font_size", _DEFAULT_SUBTITLE_STYLE["font_size"]))
        escaped = self._escape_filter_path(subtitle_path)
        force_parts = [
            f"FontSize={font_size}",
            f"PrimaryColour={self._ass_color(style.get('color', '#FFFFFF'))}",
            f"Outline={1 if font_size <= 24 else 2}" if style.get("stroke", True) else "Outline=0",
            f"Alignment={self._ass_alignment(position)}",
            f"MarginV={self._ass_margin_v(position, height)}",
            "MarginL=40",
            "MarginR=40",
        ]
        # 优先使用用户选择的字体，其次回退到 ffmpeg_font_path 配置，最后使用 SimHei
        font_family = style.get("font_family")
        if font_family:
            force_parts.append(f"FontName={font_family}")
        elif self.settings.ffmpeg_font_path:
            force_parts.append(f"FontName={Path(self.settings.ffmpeg_font_path).stem}")
        force_style = ",".join(force_parts)
        # Windows 路径必须用引号包裹，并将反斜杠转为 C\:/posix/path，否则 libass 会解析失败。
        return (
            f"subtitles='{escaped}':original_size={width}x{height}:force_style='{force_style}'"
        )

    def _ass_color(self, hex_color: str) -> str:
        """#RRGGBB -> &H00BBGGRR& ASS 颜色。"""
        value = hex_color.lstrip("#")
        if len(value) != 6:
            return "&H00FFFFFF&"
        r, g, b = value[0:2], value[2:4], value[4:6]
        return f"&H00{b}{g}{r}&"

    def _ass_alignment(self, position: str) -> int:
        """字幕位置映射 ASS Alignment。"""
        return {"bottom": 2, "middle": 5, "top": 8}.get(position, 2)

    def _ass_margin_v(self, position: str, height: int) -> int:
        """ASS 垂直边距：底部/顶部分别距画面边缘一定像素，确保字幕贴底/贴顶。"""
        if position == "top":
            return max(32, int(height * 0.04))
        if position == "middle":
            return 0
        return max(48, int(height * 0.05))

    def extract_frame(self, video_path: str, output_path: str, time_seconds: float | None = None) -> str:
        """从视频抽取单帧作为封面底图。"""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        if self.settings.use_stub_model_adapters:
            output.write_bytes(b"stub frame")
            return str(output)
        command = [self.settings.ffmpeg_command, "-y", "-i", video_path]
        if time_seconds is not None:
            command.extend(["-ss", str(time_seconds)])
        command.extend(["-frames:v", "1", str(output)])
        subprocess.run(command, check=True)
        return str(output)

    def probe_duration(self, video_path: str) -> float | None:
        """读取视频时长（秒）。"""
        try:
            result = subprocess.run(
                [
                    self.settings.ffprobe_command,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    video_path,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
            )
            return round(float(result.stdout.strip()), 2)
        except Exception:
            return None

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
        """将本地路径转为 ffmpeg subtitles 滤镜可识别的 quoted POSIX 形式。"""
        posix = Path(path).resolve().as_posix()
        if len(posix) >= 2 and posix[1] == ":":
            posix = posix[0] + "\\:" + posix[2:]
        return posix.replace("'", "\\'")
