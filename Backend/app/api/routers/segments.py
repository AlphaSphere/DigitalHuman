"""口播文案段落 HTTP 路由。

衔接 ASR/解析后的脚本编辑：查询段落、保存编辑、确认脚本并进入风险审核。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import success_response
from app.schemas.domain import ConfirmScriptRequest, UpdateSegmentsRequest
from app.services.segment_service import check_script_risk, confirm_script, list_segments, save_segments
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


@router.post("/tasks/{task_id}/check-script-risk")
def run_script_risk_check(task_id: str, db: Session = Depends(get_db)) -> dict:
    """保存当前文案并执行脚本阶段合规检查（不跳转页面）。"""
    return success_response(check_script_risk(db, task_id))


@router.post("/tasks/{task_id}/confirm-script")
def confirm(task_id: str, payload: ConfirmScriptRequest | None = None, db: Session = Depends(get_db)) -> dict:
    """确认口播脚本：通过或带提示项时进入配置，仅 blocked 需改文案。"""
    note = payload.confirmation_note if payload else None
    return success_response(task_to_dict(confirm_script(db, task_id, note)))
