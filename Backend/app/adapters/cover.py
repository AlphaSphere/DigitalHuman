"""封面生成适配器：抽帧 + Pillow 叠字。"""

from pathlib import Path

from app.adapters.ffmpeg import FFmpegAdapter
from app.adapters.llm import DeepSeekAdapter
from app.core.config import get_settings
from app.services.storage_service import task_dir, touch_file


class CoverAdapter:
    """从成片抽帧并生成封面图。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.ffmpeg = FFmpegAdapter()

    def extract_frame_candidates(self, task_id: str, video_path: str, count: int = 5) -> list[str]:
        """抽取多个候选帧。"""
        duration = self.ffmpeg.probe_duration(video_path) or 30.0
        paths: list[str] = []
        for index in range(count):
            t = duration * (index + 1) / (count + 1)
            out = task_dir(task_id) / "intermediate" / f"cover_candidate_{index + 1}.jpg"
            paths.append(self.ffmpeg.extract_frame(video_path, str(out), t))
        return paths

    def generate_cover(
        self,
        task_id: str,
        frame_path: str,
        text: str,
        highlight_words: list[str] | None = None,
        font_size: int = 60,
        font_color: str = "#FFFFFF",
        highlight_color: str = "#FFD600",
        position: str = "bottom",
        use_ai_copy: bool = False,
        script: str | None = None,
    ) -> str:
        """在帧图上绘制封面文案。"""
        if use_ai_copy and script:
            copy = DeepSeekAdapter().generate_cover_copy(script, highlight_words)
            text = copy["cover_text"]
            highlight_words = copy.get("highlight_words") or highlight_words

        output = task_dir(task_id) / "output" / "cover.jpg"
        output.parent.mkdir(parents=True, exist_ok=True)

        if self.settings.use_stub_model_adapters:
            return touch_file(task_id, "output/cover.jpg", b"stub cover")

        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as exc:
            raise RuntimeError("封面生成需要安装 Pillow") from exc

        image = Image.open(frame_path).convert("RGB")
        draw = ImageDraw.Draw(image)
        font_path = self.settings.ffmpeg_font_path
        try:
            font = ImageFont.truetype(str(font_path), font_size) if font_path else ImageFont.load_default()
        except OSError:
            font = ImageFont.load_default()

        width, height = image.size
        y_map = {"top": int(height * 0.12), "center": int(height * 0.45), "bottom": int(height * 0.72)}
        y = y_map.get(position, y_map["bottom"])
        x = int(width * 0.08)
        max_width = int(width * 0.84)

        # 高亮词：按词组绘制，命中 highlight_words 的片段使用 highlight_color
        highlights = [word.strip() for word in (highlight_words or []) if word and word.strip()]
        if highlights:
            self._draw_text_with_highlights(
                draw,
                text,
                highlights,
                font,
                x,
                y,
                max_width,
                font_color,
                highlight_color,
            )
        else:
            draw.text(
                (x, y),
                text,
                font=font,
                fill=font_color,
                stroke_width=2,
                stroke_fill="#000000",
            )

        image.save(output, format="JPEG", quality=92)
        return str(output)

    def _draw_text_with_highlights(
        self,
        draw,
        text: str,
        highlights: list[str],
        font,
        x: int,
        y: int,
        max_width: int,
        font_color: str,
        highlight_color: str,
    ) -> None:
        """逐段绘制封面文案，支持多个高亮词。"""
        cursor_x = x
        cursor_y = y
        remaining = text
        sorted_highlights = sorted(highlights, key=len, reverse=True)

        while remaining:
            match_index = len(remaining)
            match_word = ""
            for word in sorted_highlights:
                idx = remaining.find(word)
                if idx != -1 and idx < match_index:
                    match_index = idx
                    match_word = word

            prefix = remaining[:match_index]
            if prefix:
                cursor_x, cursor_y = self._draw_text_segment(
                    draw,
                    prefix,
                    font,
                    cursor_x,
                    cursor_y,
                    max_width,
                    font_color,
                    x,
                )

            if match_word:
                cursor_x, cursor_y = self._draw_text_segment(
                    draw,
                    match_word,
                    font,
                    cursor_x,
                    cursor_y,
                    max_width,
                    highlight_color,
                    x,
                )
                remaining = remaining[match_index + len(match_word) :]
            else:
                cursor_x, cursor_y = self._draw_text_segment(
                    draw,
                    remaining,
                    font,
                    cursor_x,
                    cursor_y,
                    max_width,
                    font_color,
                    x,
                )
                break

    def _draw_text_segment(
        self,
        draw,
        segment: str,
        font,
        cursor_x: int,
        cursor_y: int,
        max_width: int,
        color: str,
        line_start_x: int,
    ) -> tuple[int, int]:
        for char in segment:
            char_width = int(draw.textlength(char, font=font))
            if cursor_x + char_width > line_start_x + max_width:
                cursor_x = line_start_x
                cursor_y += int(draw.textbbox((0, 0), "测", font=font)[3] * 1.2)
            draw.text(
                (cursor_x, cursor_y),
                char,
                font=font,
                fill=color,
                stroke_width=2,
                stroke_fill="#000000",
            )
            cursor_x += char_width
        return cursor_x, cursor_y
