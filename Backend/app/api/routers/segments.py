"""口播文案段落 HTTP 路由。

衔接 ASR/解析后的脚本编辑：查询段落、保存编辑、确认脚本并进入风险审核。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import success_response
from app.schemas.domain import UpdateSegmentsRequest
from app.services.segment_service import confirm_script, list_segments, save_segments
from app.services.serializers import task_to_dict

router = APIRouter()


@router.get("/tasks/{task_id}/segments")
def get_segments(task_id: str, db: Session = Depends(get_db)) -> dict:
    """获取任务下全部文案段落。

    用途：
        脚本编辑页加载分段列表与时间轴。

    参数：
        task_id: 任务 ID。
        db: 数据库会话。

    返回：
        segments 数组的 success_response。

    逻辑：
        委托 segment_service.list_segments。
    """
    return success_response(list_segments(db, task_id))


@router.put("/tasks/{task_id}/segments")
def update_segments(task_id: str, payload: UpdateSegmentsRequest, db: Session = Depends(get_db)) -> dict:
    """全量保存用户编辑后的文案段落。

    用途：
        用户调整分段、文案或时间轴后的持久化。

    参数：
        task_id: 任务 ID。
        payload: UpdateSegmentsRequest JSON 体。
        db: 数据库会话。

    返回：
        保存后的 segments 列表。

    逻辑：
        委托 save_segments，可能抛 VALIDATION_ERROR。
    """
    return success_response(save_segments(db, task_id, payload))


@router.post("/tasks/{task_id}/confirm-script")
def confirm(task_id: str, db: Session = Depends(get_db)) -> dict:
    """确认口播脚本并触发脚本阶段风险扫描。

    用途：
        文案定稿后进入 risk_service 脚本审核，更新任务状态。

    参数：
        task_id: 任务 ID。
        db: 数据库会话。

    返回：
        更新后的任务 dict（含新 status）。

    逻辑：
        confirm_script 内 replace_risk_check(script)。
    """
    return success_response(task_to_dict(confirm_script(db, task_id)))
