"""任务状态守卫：生成阶段禁止改文案、合规确认前置校验等。"""

from datetime import datetime, timedelta

from app.core.exceptions import ApiError
from app.db.models import TaskModel
from app.domain.enums import TaskStatus

# 生成流水线进行中的状态
GENERATION_PHASE_STATUSES = frozenset(
    {
        TaskStatus.dubbing.value,
        TaskStatus.dubbed.value,
        TaskStatus.avatar_generating.value,
        TaskStatus.avatar_generated.value,
        TaskStatus.subtitle_generating.value,
        TaskStatus.composing.value,
        TaskStatus.retrying.value,
    }
)

# 允许编辑文案 / 跑 script 合规的状态
PRE_GENERATION_EDITABLE_STATUSES = frozenset(
    {
        TaskStatus.uploaded.value,
        TaskStatus.audio_extracted.value,
        TaskStatus.transcribing.value,
        TaskStatus.transcribed.value,
        TaskStatus.script_pasted.value,
        TaskStatus.script_parsing.value,
        TaskStatus.script_parsed.value,
        TaskStatus.script_confirmed.value,
        TaskStatus.content_checking.value,
        TaskStatus.content_review_required.value,
        TaskStatus.content_rejected.value,
        TaskStatus.failed.value,
    }
)

# 允许 script 阶段人工确认风险的状态
SCRIPT_RISK_CONFIRM_STATUSES = frozenset(
    {
        TaskStatus.transcribed.value,
        TaskStatus.script_parsed.value,
        TaskStatus.content_review_required.value,
        TaskStatus.script_confirmed.value,
        TaskStatus.failed.value,
    }
)

STALE_GENERATION_MINUTES = 15


def is_generation_phase(status: str | None) -> bool:
    return status in GENERATION_PHASE_STATUSES


def assert_not_in_generation(task: TaskModel, action: str) -> None:
    """生成进行中禁止改文案、重识别或重新跑合规。"""
    if is_generation_phase(task.status):
        raise ApiError(
            "GENERATION_IN_PROGRESS",
            f"任务正在生成中，暂不可{action}。请等待完成或到进度页强制重试。",
            409,
        )


def assert_can_confirm_script_risk(task: TaskModel) -> None:
    """script 阶段人工确认前校验任务未处于生成中。"""
    if is_generation_phase(task.status):
        raise ApiError("GENERATION_IN_PROGRESS", "任务正在生成中，无法变更合规确认", 409)
    if task.status not in SCRIPT_RISK_CONFIRM_STATUSES:
        raise ApiError("VALIDATION_ERROR", "当前任务状态不允许确认文案合规", 409)


def is_stale_generation(task: TaskModel, minutes: int = STALE_GENERATION_MINUTES) -> bool:
    """生成中状态长时间未更新，视为 worker 卡住。"""
    if not is_generation_phase(task.status):
        return False
    if not task.updated_at:
        return False
    return datetime.utcnow() - task.updated_at > timedelta(minutes=minutes)


def assert_can_retry_generation(task: TaskModel) -> None:
    """校验是否允许触发生成重试。"""
    if task.status == TaskStatus.retrying.value:
        raise ApiError("VALIDATION_ERROR", "任务正在重试中，请勿重复提交", 409)
    if task.status == TaskStatus.failed.value:
        if task.error_code == "TRANSCRIBE_FAILED":
            raise ApiError(
                "TRANSCRIBE_FAILED",
                "识别失败请使用重新识别接口，而非生成重试",
                409,
            )
        return
    if is_generation_phase(task.status) and is_stale_generation(task):
        return
    if task.status in GENERATION_PHASE_STATUSES:
        raise ApiError("GENERATION_IN_PROGRESS", "任务仍在生成中，请稍后再试或等待超时后强制重试", 409)
    raise ApiError("VALIDATION_ERROR", "仅失败或卡住超时的生成任务可重新生成", 409)
