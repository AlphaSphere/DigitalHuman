import subprocess
from pathlib import Path

from app.core.config import get_settings


SUPPORTED_MUSIC_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def list_music_tracks() -> list[dict]:
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
    return path.stem.replace("_", " ").replace("-", " ").strip().title()


def _duration_seconds(ffprobe_command: str, path: Path) -> float | None:
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
