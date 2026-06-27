"""背景音乐库 HTTP 路由。

扫描本地 CC0 音乐目录，供生成配置时选择 background_music_path；
支持用户自定义上传 BGM 文件到音乐库。
"""

import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.exceptions import success_response
from app.services.music_service import SUPPORTED_MUSIC_EXTENSIONS, list_music_tracks

router = APIRouter()


@router.get("/music-tracks")
def music_tracks() -> dict:
    """返回可选背景音乐曲目列表。

    用途：
        生成配置界面展示曲名、路径、时长。

    参数：
        无。

    返回：
        曲目 dict 数组的 success_response。

    逻辑：
        委托 music_service.list_music_tracks，无数据库依赖。
    """
    return success_response(list_music_tracks())


@router.post("/music-tracks/upload")
async def upload_music_track(file: UploadFile) -> dict:
    """上传用户自定义 BGM 文件到音乐库目录。

    用途：
        允许用户将本地音频文件（MP3/WAV/M4A 等）上传到音乐库，
        上传后即可在背景音乐列表中选择。

    参数：
        file: 音频文件，支持 mp3/wav/m4a/aac/flac/ogg。

    返回：
        新增曲目信息的 success_response。

    逻辑：
        校验扩展名 → 保存到 MUSIC_LIBRARY_PATH → 返回曲目元数据。
    """
    settings = get_settings()
    original_name = Path(file.filename or "upload")
    suffix = original_name.suffix.lower()
    if suffix not in SUPPORTED_MUSIC_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的音频格式 {suffix}，请上传 {'/'.join(SUPPORTED_MUSIC_EXTENSIONS)} 文件",
        )

    music_dir = settings.music_library_path
    music_dir.mkdir(parents=True, exist_ok=True)

    # 避免同名覆盖：若已存在则追加序号
    dest = music_dir / original_name.name
    counter = 1
    while dest.exists():
        dest = music_dir / f"{original_name.stem}_{counter}{suffix}"
        counter += 1

    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    return success_response(
        {
            "id": dest.stem,
            "name": dest.stem.replace("_", " ").replace("-", " ").strip().title(),
            "path": str(dest),
            "source": "user-upload",
            "duration": None,
        }
    )
