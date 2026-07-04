"""覆盖 app/services/task_guards.py 里的状态机守卫逻辑，构造 TaskModel 不落库。"""

from datetime import datetime, timedelta

import pytest

from app.core.exceptions import ApiError
from app.db.models import TaskModel
from app.domain.enums import TaskStatus
from app.services.task_guards import (
    STALE_GENERATION_MINUTES,
    assert_can_retry_generation,
    assert_can_confirm_script_risk,
    assert_not_in_generation,
    is_generation_phase,
    is_stale_generation,
)


def make_task(status: str, error_code: str | None = None, updated_at: datetime | None = None) -> TaskModel:
    return TaskModel(id="t1", script_source="script_pasted", status=status, error_code=error_code, updated_at=updated_at)


@pytest.mark.parametrize(
    "status,expected",
    [
        (TaskStatus.dubbing.value, True),
        (TaskStatus.composing.value, True),
        (TaskStatus.retrying.value, True),
        (TaskStatus.uploaded.value, False),
        (TaskStatus.completed.value, False),
        (None, False),
    ],
)
def test_is_generation_phase(status, expected):
    assert is_generation_phase(status) is expected


def test_assert_not_in_generation_blocks_during_generation():
    task = make_task(TaskStatus.dubbing.value)
    with pytest.raises(ApiError) as exc_info:
        assert_not_in_generation(task, "编辑文案")
    assert exc_info.value.code == "GENERATION_IN_PROGRESS"


def test_assert_not_in_generation_allows_outside_generation():
    task = make_task(TaskStatus.script_confirmed.value)
    assert_not_in_generation(task, "编辑文案")  # 不应抛异常


def test_assert_can_confirm_script_risk_rejects_during_generation():
    task = make_task(TaskStatus.avatar_generating.value)
    with pytest.raises(ApiError) as exc_info:
        assert_can_confirm_script_risk(task)
    assert exc_info.value.code == "GENERATION_IN_PROGRESS"


def test_assert_can_confirm_script_risk_rejects_wrong_status():
    task = make_task(TaskStatus.completed.value)
    with pytest.raises(ApiError) as exc_info:
        assert_can_confirm_script_risk(task)
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_assert_can_confirm_script_risk_allows_valid_status():
    task = make_task(TaskStatus.transcribed.value)
    assert_can_confirm_script_risk(task)  # 不应抛异常


def test_is_stale_generation_false_when_not_in_generation_phase():
    task = make_task(TaskStatus.completed.value, updated_at=datetime.utcnow() - timedelta(hours=1))
    assert is_stale_generation(task) is False


def test_is_stale_generation_false_when_updated_at_missing():
    task = make_task(TaskStatus.dubbing.value, updated_at=None)
    assert is_stale_generation(task) is False


def test_is_stale_generation_false_when_recent():
    task = make_task(TaskStatus.dubbing.value, updated_at=datetime.utcnow())
    assert is_stale_generation(task) is False


def test_is_stale_generation_true_when_older_than_threshold():
    task = make_task(
        TaskStatus.dubbing.value,
        updated_at=datetime.utcnow() - timedelta(minutes=STALE_GENERATION_MINUTES + 1),
    )
    assert is_stale_generation(task) is True


def test_assert_can_retry_generation_rejects_when_already_retrying():
    task = make_task(TaskStatus.retrying.value)
    with pytest.raises(ApiError) as exc_info:
        assert_can_retry_generation(task)
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_assert_can_retry_generation_redirects_transcribe_failed():
    task = make_task(TaskStatus.failed.value, error_code="TRANSCRIBE_FAILED")
    with pytest.raises(ApiError) as exc_info:
        assert_can_retry_generation(task)
    assert exc_info.value.code == "TRANSCRIBE_FAILED"


def test_assert_can_retry_generation_allows_other_failed_reasons():
    task = make_task(TaskStatus.failed.value, error_code="TTS_FAILED")
    assert_can_retry_generation(task)  # 不应抛异常


def test_assert_can_retry_generation_allows_stale_generation():
    task = make_task(
        TaskStatus.avatar_generating.value,
        updated_at=datetime.utcnow() - timedelta(minutes=STALE_GENERATION_MINUTES + 5),
    )
    assert_can_retry_generation(task)  # 不应抛异常，卡住超时允许强制重试


def test_assert_can_retry_generation_rejects_fresh_generation_in_progress():
    task = make_task(TaskStatus.avatar_generating.value, updated_at=datetime.utcnow())
    with pytest.raises(ApiError) as exc_info:
        assert_can_retry_generation(task)
    assert exc_info.value.code == "GENERATION_IN_PROGRESS"


def test_assert_can_retry_generation_rejects_other_statuses():
    task = make_task(TaskStatus.script_confirmed.value)
    with pytest.raises(ApiError) as exc_info:
        assert_can_retry_generation(task)
    assert exc_info.value.code == "VALIDATION_ERROR"
