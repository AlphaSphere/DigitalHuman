"""内容风险审核服务。

贯穿任务生命周期两阶段：
- script：用户确认口播文案后，扫描敏感词/隐私/平台规则；
- pre_publish：分发前校验标题、简介与 AI 标识确认。
审核结果驱动任务状态（通过 / 待人工 / 拦截）。
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adapters.llm import DeepSeekAdapter
from app.core.exceptions import ApiError
from app.db.models import ArtifactModel, RiskCheckModel, RiskFindingModel, TaskModel
from app.domain.enums import ArtifactType, ReviewedBy, RiskLevel, RiskStage, RiskStatus, RiskType, TaskStatus
from app.services.id_service import create_id
from app.services.task_guards import assert_can_confirm_script_risk

_VALID_RISK_TYPES = {item.value for item in RiskType}
_VALID_RISK_STATUSES = {item.value for item in RiskStatus}


def _format_finding_position(script_text: str, start: int, end: int, line: int, text: str) -> str:
    """生成可解析且可读的位置描述。"""
    snippet = text or script_text[start:end]
    snippet = snippet.replace("\n", " ")[:24]
    return f"char:{start}-{end}|line:{line}|第 {line} 行 ·「{snippet}」"


def _format_meta_finding_position(scope: str, label: str) -> str:
    """非正文命中项（如发布说明）的位置描述。"""
    return f"meta:{scope}|{label}|发布环节要求（非正文词句）"


def _resolve_text_span(script_text: str, text: str, start: int | None, end: int | None) -> tuple[int, int, int] | None:
    """解析正文中的命中区间；无法定位则返回 None。"""
    cleaned = text.strip()
    if not cleaned:
        return None

    if isinstance(start, int) and isinstance(end, int):
        start = max(0, min(start, len(script_text)))
        end = max(start, min(end, len(script_text)))
        if end > start and script_text[start:end]:
            line = script_text[:start].count("\n") + 1
            return start, end, line

    index = script_text.find(cleaned)
    if index < 0:
        return None
    end_index = index + len(cleaned)
    line = script_text[:index].count("\n") + 1
    return index, end_index, line


def build_script_findings_ai(task_id: str, script_text: str) -> tuple[list[dict], RiskStatus]:
    """调用 DeepSeek 对文案做 AI 合规审查。"""
    adapter = DeepSeekAdapter()
    if not adapter.is_configured():
        raise ApiError(
            "DEEPSEEK_NOT_CONFIGURED",
            "DeepSeek 未配置，无法运行 AI 合规检查。请在 .env 设置 DEEPSEEK_API_KEY 后重启。",
            503,
        )

    try:
        payload = adapter.check_script_compliance(script_text)
    except RuntimeError as exc:
        raise ApiError("DEEPSEEK_FAILED", str(exc), 502) from exc

    findings: list[dict] = []
    for index, item in enumerate(payload.get("findings") or []):
        if not isinstance(item, dict):
            continue
        risk_type = str(item.get("type") or RiskType.platform_rule.value)
        if risk_type not in _VALID_RISK_TYPES:
            risk_type = RiskType.platform_rule.value

        text = str(item.get("text") or item.get("quote") or "").strip()
        suggestion = str(item.get("suggestion") or "请修改相关表述后重新检查。")
        in_script = item.get("in_script")
        if in_script is False:
            in_script = False
        elif text:
            in_script = text in script_text
        else:
            in_script = False

        if in_script and text:
            span = _resolve_text_span(script_text, text, item.get("start"), item.get("end"))
            if span:
                start, end, line = span
                findings.append(
                    {
                        "id": f"{create_id('finding')}_{index}",
                        "type": risk_type,
                        "target": "script",
                        "text": script_text[start:end],
                        "position": _format_finding_position(script_text, start, end, line, script_text[start:end]),
                        "suggestion": suggestion,
                    }
                )
                continue

        scope = str(item.get("scope") or "publish")
        label = str(item.get("position_label") or "发布说明")
        findings.append(
            {
                "id": f"{create_id('finding')}_{index}",
                "type": risk_type,
                "target": scope,
                "text": text or "发布合规提示",
                "position": _format_meta_finding_position(scope, label),
                "suggestion": suggestion,
            }
        )

    status_raw = str(payload.get("overall_status") or "").strip()
    if status_raw in _VALID_RISK_STATUSES:
        risk_status = RiskStatus(status_raw)
    else:
        risk_status = derive_risk_status(findings)
    return findings, risk_status


def build_script_findings_for_check(task_id: str, script_text: str) -> tuple[list[dict], RiskStatus, ReviewedBy]:
    """统一文案合规入口：有 DeepSeek 用 AI，否则回退关键词规则。"""
    adapter = DeepSeekAdapter()
    if adapter.is_configured():
        findings, risk_status = build_script_findings_ai(task_id, script_text)
        return findings, risk_status, ReviewedBy.deepseek
    findings = build_script_findings(task_id, script_text)
    return findings, derive_risk_status(findings), ReviewedBy.system


def resolve_script_risk_check_mode() -> str:
    """返回当前合规检查模式：ai 或 rules。"""
    return "ai" if DeepSeekAdapter().is_configured() else "rules"


def build_script_findings(task_id: str, script_text: str) -> list[dict]:
    """根据口播全文构建脚本阶段风险发现项。

    用途：
        在 confirm_script 时扫描文案，生成待写入 RiskFindingModel 的字典列表。

    参数：
        task_id: 任务 ID（用于生成 finding id 后缀片段）。
        script_text: 合并后的口播全文。

    返回：
        finding dict 列表（含 type、target、text、position、suggestion）。

    逻辑：
        按预设关键词规则匹配位置并追加建议；
        无论是否命中关键词，均追加「AI 生成标识」平台规则提示项。
    """
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
    """根据脚本阶段发现项推导整体风险状态。

    用途：
        replace_risk_check 在 stage=script 时决定 risk_status 与任务流转。

    参数：
        findings: build_script_findings 等产生的发现项列表。

    返回：
        RiskStatus 枚举：含隐私类则 blocked，有其它项则 manual_review，否则 passed。

    逻辑：
        隐私类（身份证、手机号等）直接拦截；其余命中进入人工复核；无命中则通过。
    """
    if any(finding["type"] == RiskType.privacy.value for finding in findings):
        return RiskStatus.blocked
    if findings:
        return RiskStatus.manual_review
    return RiskStatus.passed


def replace_risk_check(
    db: Session,
    task_id: str,
    stage: RiskStage,
    findings: list[dict],
    risk_status_override: RiskStatus | None = None,
    reviewed_by: ReviewedBy = ReviewedBy.system,
) -> RiskCheckModel:
    """为任务写入新一轮风险审核记录及关联发现项。

    用途：
        脚本确认或发布前检查时，替换/新增当前 stage 的 RiskCheck 快照（先 flush 再挂 findings）。

    参数：
        db: 数据库会话（调用方负责 commit）。
        task_id: 任务 ID。
        stage: 审核阶段（script / pre_publish）。
        findings: 发现项 dict 列表。

    返回：
        已 flush 的 RiskCheckModel（含 findings 子记录）。

    逻辑：
        按 stage 选择 derive_risk_status 或 derive_pre_publish_status；
        计算 risk_level、risk_types，创建 RiskCheckModel 并批量插入 RiskFindingModel。
    """
    risk_status = risk_status_override or (
        derive_risk_status(findings) if stage == RiskStage.script else derive_pre_publish_status(findings)
    )
    risk_check = RiskCheckModel(
        id=create_id("risk"),
        task_id=task_id,
        stage=stage.value,
        risk_status=risk_status.value,
        risk_level=(RiskLevel.high if risk_status == RiskStatus.blocked else RiskLevel.medium if findings else RiskLevel.low).value,
        risk_types=sorted({finding["type"] for finding in findings}),
        reviewed_by=reviewed_by.value,
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
    """根据发布前发现项推导风险状态。

    用途：
        pre_publish 阶段 replace_risk_check 的状态计算。

    参数：
        findings: build_pre_publish_findings 产生的列表。

    返回：
        含敏感词为 warning，其它非空为 manual_review，否则 passed。

    逻辑：
        发布前隐私拦截规则弱于脚本阶段，敏感词以警告为主。
    """
    if any(finding["type"] == RiskType.sensitive_keyword.value for finding in findings):
        return RiskStatus.warning
    if findings:
        return RiskStatus.manual_review
    return RiskStatus.passed


def build_pre_publish_findings(input_data) -> list[dict]:
    """根据发布元信息构建发布前风险发现项。

    用途：
        POST pre-publish-check 时校验 AI 标识确认与标题/简介用词。

    参数：
        input_data: PrePublishCheckInput（含 ai_label_confirmed、title、description 等）。

    返回：
        finding dict 列表，可能为空。

    逻辑：
        未确认 AI 标识则追加平台规则项；
        标题含「最强」或简介含「收益」则追加敏感词项并区分 target。
    """
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
    """查询任务的风险审核历史记录。

    用途：
        API 列表展示某任务全部或指定阶段的审核记录及 findings。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。
        stage: 可选，按阶段过滤（script / pre_publish）。

    返回：
        RiskCheckModel 列表，按 created_at 降序，预加载 findings。

    逻辑：
        selectinload 避免 N+1；有 stage 时追加 where 条件。
    """
    query = select(RiskCheckModel).options(selectinload(RiskCheckModel.findings)).where(RiskCheckModel.task_id == task_id)
    if stage:
        query = query.where(RiskCheckModel.stage == stage.value)
    return list(db.scalars(query.order_by(RiskCheckModel.created_at.desc())).all())


def confirm_risk_check(db: Session, task_id: str, risk_check_id: str, confirmation_note: str) -> tuple[TaskModel, RiskCheckModel]:
    """人工确认通过某条风险审核记录并推进任务状态。

    用途：
        内容待复核时，运营/用户填写说明后放行，进入 script_confirmed 或 publish_ready。

    参数：
        db: 数据库会话（本函数内 commit）。
        task_id: 任务 ID。
        risk_check_id: 要确认的风险记录 ID。
        confirmation_note: 人工确认说明，不可为空。

    返回：
        (更新后的 TaskModel, 更新后的 RiskCheckModel)。

    逻辑：
        校验记录存在、非 blocked、说明非空；
        将 risk_status 置为 passed，reviewed_by 置 user，并按 stage 更新 task.status。
    """
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
    if risk_check.stage == RiskStage.script.value:
        assert_can_confirm_script_risk(task)
    elif risk_check.stage == RiskStage.pre_publish.value:
        if task.status != TaskStatus.completed.value:
            raise ValueError("请先完成视频生成后再进行发布前检查")
        final_video = db.scalar(
            select(ArtifactModel).where(
                ArtifactModel.task_id == task_id,
                ArtifactModel.type == ArtifactType.final_video.value,
            )
        )
        if not final_video:
            raise ValueError("未找到成片产物，无法确认发布前合规")
    risk_check.risk_status = RiskStatus.passed.value
    risk_check.reviewed_by = ReviewedBy.user.value
    risk_check.reviewed_at = datetime.utcnow()
    task.status = TaskStatus.publish_ready.value if risk_check.stage == RiskStage.pre_publish.value else TaskStatus.script_confirmed.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(risk_check)
    return task, risk_check
