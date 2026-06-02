"""音色与数字人形象档案 HTTP 路由。

为生成配置阶段提供可选 voice_profile / avatar_profile 列表，数据来自预置种子或管理端维护。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import success_response
from app.services.profile_service import list_avatar_profiles, list_voice_profiles

router = APIRouter()


@router.get("/voice-profiles")
def voices(db: Session = Depends(get_db)) -> dict:
    """列出全部音色档案。

    用途：
        生成配置页「选择音色」数据源。

    参数：
        db: 数据库会话。

    返回：
        音色档案对象数组的 success_response。

    逻辑：
        只读查询，无分页。
    """
    return success_response(list_voice_profiles(db))


@router.get("/avatar-profiles")
def avatars(db: Session = Depends(get_db)) -> dict:
    """列出全部数字人形象档案。

    用途：
        生成配置页「选择形象」数据源。

    参数：
        db: 数据库会话。

    返回：
        形象档案对象数组的 success_response。

    逻辑：
        只读查询，无分页。
    """
    return success_response(list_avatar_profiles(db))
