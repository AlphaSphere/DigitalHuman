"""背景音乐库扫描服务。

在保存生成配置时，用户可从本地 CC0 音乐库选择 background_music_path；
本模块负责枚举曲目并解析时长供前端展示。
"""

import subprocess
from pathlib import Path

from app.core.config import get_settings


# 音乐库扫描支持的音频扩展名
SUPPORTED_MUSIC_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def list_music_tracks() -> list[dict]:
    """扫描配置的音乐库目录并返回曲目列表。

    用途：
        生成配置界面展示可选背景音乐（id、名称、路径、时长）。

    参数：
        无（路径与 ffprobe 命令从应用配置读取）。

    返回：
        曲目 dict 列表；库目录不存在时返回空列表。

    逻辑：
        递归遍历 music_library_path 下支持扩展名的文件；
        对每条记录调用 ffprobe 解析时长，失败时 duration 为 None。
    """
    settings = get_settings()
    root = settings.music_library_path
    tracks = []
    if not root.exists():
        return tracks
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_MUSIC_EXTENSIONS:
            tracks.append(
                {
                    "id": path.stem,
                    "name": _display_name(path),
                    "path": str(path),
                    "source": "CC0-1.0 Music",
                    "duration": _duration_seconds(settings.ffprobe_command, path),
                }
            )
    return tracks


def _display_name(path: Path) -> str:
    """将文件名 stem 格式化为展示用曲目名。"""
    return path.stem.replace("_", " ").replace("-", " ").strip().title()


def pick_random_music_track() -> dict | None:
    """从音乐库随机选择一首曲目。"""
    import random

    tracks = list_music_tracks()
    if not tracks:
        return None
    return random.choice(tracks)


def resolve_background_music_path(mode: str | None, fixed_path: str | None) -> str | None:
    """根据背景音乐模式解析实际文件路径。"""
    from app.domain.enums import BackgroundMusicMode

    if mode == BackgroundMusicMode.random.value or mode == "random":
        track = pick_random_music_track()
        return track["path"] if track else None
    if mode == BackgroundMusicMode.none.value or mode == "none":
        return None
    return fixed_path


def _duration_seconds(ffprobe_command: str, path: Path) -> float | None:
    """通过 ffprobe 读取音频时长（秒），失败返回 None。"""
    try:
        result = subprocess.run(
            [
                ffprobe_command,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except Exception:
        return None
    try:
        return round(float(result.stdout.strip()), 2)
    except ValueError:
        return None
