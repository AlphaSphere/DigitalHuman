from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import RiskCheckModel, RiskFindingModel, TaskModel
from app.domain.enums import ReviewedBy, RiskLevel, RiskStage, RiskStatus, RiskType, TaskStatus
from app.services.id_service import create_id


def build_script_findings(task_id: str, script_text: str) -> list[dict]:
    rules = [
        ("收益", RiskType.platform_rule, "避免承诺固定收益，建议改成更中性的经验分享表述。"),
        ("最强", RiskType.sensitive_keyword, "广告法极限词建议替换为“较强”或具体事实描述。"),
        ("身份证", RiskType.privacy, "请删除或打码个人身份信息。"),
        ("手机号", RiskType.privacy, "请删除手机号或改为非真实示例。"),
    ]
    findings = []
    for keyword, risk_type, suggestion in rules:
        position = script_text.find(keyword)
        if position >= 0:
            findings.append(
                {
                    "id": f"{create_id('finding')}_{task_id[-4:]}",
                    "type": risk_type.value,
                    "target": "script",
                    "text": keyword,
                    "position": f"文案第 {position + 1} 个字符附近",
                    "suggestion": suggestion,
                }
            )
    findings.append(
        {
            "id": f"{create_id('finding')}_{task_id[-4:]}",
            "type": RiskType.platform_rule.value,
            "target": "script",
            "text": "AI 生成标识",
            "position": "发布说明",
            "suggestion": "建议在标题、简介或画面中标注 AI 数字人 / AI 配音内容。",
        }
    )
    return findings


def derive_risk_status(findings: list[dict]) -> RiskStatus:
    if any(finding["type"] == RiskType.privacy.value for finding in findings):
        return RiskStatus.blocked
    if findings:
        return RiskStatus.manual_review
    return RiskStatus.passed


def replace_risk_check(db: Session, task_id: str, stage: RiskStage, findings: list[dict]) -> RiskCheckModel:
    risk_status = derive_risk_status(findings) if stage == RiskStage.script else derive_pre_publish_status(findings)
    risk_check = RiskCheckModel(
        id=create_id("risk"),
        task_id=task_id,
        stage=stage.value,
        risk_status=risk_status.value,
        risk_level=(RiskLevel.high if risk_status == RiskStatus.blocked else RiskLevel.medium if findings else RiskLevel.low).value,
        risk_types=sorted({finding["type"] for finding in findings}),
        reviewed_by=ReviewedBy.system.value,
        reviewed_at=None,
        created_at=datetime.utcnow(),
    )
    db.add(risk_check)
    db.flush()
    for finding in findings:
        db.add(RiskFindingModel(risk_check_id=risk_check.id, **finding))
    db.flush()
    return risk_check


def derive_pre_publish_status(findings: list[dict]) -> RiskStatus:
    if any(finding["type"] == RiskType.sensitive_keyword.value for finding in findings):
        return RiskStatus.warning
    if findings:
        return RiskStatus.manual_review
    return RiskStatus.passed


def build_pre_publish_findings(input_data) -> list[dict]:
    findings = []
    if not input_data.ai_label_confirmed:
        findings.append(
            {
                "id": create_id("finding"),
                "type": RiskType.platform_rule.value,
                "target": "ai_label",
                "text": "AI 生成标识未确认",
                "position": "发布信息",
                "suggestion": "建议在标题、简介或视频画面中明确标注 AI 生成内容。",
            }
        )
    if "最强" in input_data.title or "收益" in input_data.description:
        is_title = "最强" in input_data.title
        findings.append(
            {
                "id": create_id("finding"),
                "type": RiskType.sensitive_keyword.value,
                "target": "title" if is_title else "description",
                "text": "最强" if is_title else "收益",
                "position": "标题" if is_title else "简介",
                "suggestion": "发布前建议替换极限词或收益承诺类表述。",
            }
        )
    return findings


def get_risk_checks(db: Session, task_id: str, stage: RiskStage | None = None) -> list[RiskCheckModel]:
    query = select(RiskCheckModel).options(selectinload(RiskCheckModel.findings)).where(RiskCheckModel.task_id == task_id)
    if stage:
        query = query.where(RiskCheckModel.stage == stage.value)
    return list(db.scalars(query.order_by(RiskCheckModel.created_at.desc())).all())


def confirm_risk_check(db: Session, task_id: str, risk_check_id: str, confirmation_note: str) -> tuple[TaskModel, RiskCheckModel]:
    risk_check = db.scalar(
        select(RiskCheckModel)
        .options(selectinload(RiskCheckModel.findings))
        .where(RiskCheckModel.task_id == task_id, RiskCheckModel.id == risk_check_id)
    )
    if not risk_check:
        raise ValueError("风险审核记录不存在")
    if risk_check.risk_status == RiskStatus.blocked.value:
        raise ValueError("高风险内容不能人工放行，请先修改内容")
    if not confirmation_note.strip():
        raise ValueError("请填写确认说明")
    task = db.get(TaskModel, task_id)
    if not task:
        raise ValueError("任务不存在")
    risk_check.risk_status = RiskStatus.passed.value
    risk_check.reviewed_by = ReviewedBy.user.value
    risk_check.reviewed_at = datetime.utcnow()
    task.status = TaskStatus.publish_ready.value if risk_check.stage == RiskStage.pre_publish.value else TaskStatus.script_confirmed.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(risk_check)
    return task, risk_check
