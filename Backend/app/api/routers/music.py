"""背景音乐库 HTTP 路由。

扫描本地 CC0 音乐目录，供生成配置时选择 background_music_path。
"""

from fastapi import APIRouter

from app.core.exceptions import success_response
from app.services.music_service import list_music_tracks

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
