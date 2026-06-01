from pathlib import Path
from shutil import copyfileobj

from fastapi import UploadFile

from app.core.config import get_settings


def task_dir(task_id: str) -> Path:
    root = get_settings().storage_root / "tasks" / task_id
    for child in ("input", "intermediate", "output"):
        (root / child).mkdir(parents=True, exist_ok=True)
    return root


def safe_name(filename: str | None, fallback: str) -> str:
    if not filename:
        return fallback
    suffix = Path(filename).suffix.lower()
    return f"{fallback}{suffix}" if suffix else fallback


def save_upload(task_id: str, upload: UploadFile, name: str) -> str:
    path = task_dir(task_id) / "input" / safe_name(upload.filename, name)
    with path.open("wb") as target:
        copyfileobj(upload.file, target)
    return str(path)


def write_text(task_id: str, relative: str, content: str) -> str:
    path = task_dir(task_id) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def touch_file(task_id: str, relative: str, content: bytes = b"") -> str:
    path = task_dir(task_id) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)
