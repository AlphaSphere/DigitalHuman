"""ORM 模型 → API 响应字典的序列化层。

将 Task、Segment、Artifact、Risk、Profile、Distribution 等实体转为
路由层 success_response 可直接返回的 plain dict，保持字段命名与前端契约一致。
"""

from app.db.models import (
    ArtifactModel,
    AvatarProfileModel,
    DistributionRecordModel,
    RiskCheckModel,
    RiskFindingModel,
    ScriptSegmentModel,
    TaskModel,
    VoiceProfileModel,
)


def task_to_dict(task: TaskModel) -> dict:
    """将任务 ORM 转为 API 任务详情字典。

    用途：
        任务创建、查询、生成配置、重试等接口的统一任务体结构。

    参数：
        task: TaskModel 实例。

    返回：
        含脚本来源、状态、生成配置、错误信息、时间戳等字段的 dict。

    逻辑：
        逐字段映射 model 属性，不包含 progress（由 get_task_payload 合并）。
    """
    return {
        "id": task.id,
        "script_source": task.script_source,
        "script_generation_mode": task.script_generation_mode,
        "status": task.status,
        "source_video_path": task.source_video_path,
        "duration": task.duration,
        "aspect_ratio": task.aspect_ratio,
        "generation_voice_mode": task.generation_voice_mode,
        "custom_voice_path": task.custom_voice_path,
        "generation_video_mode": task.generation_video_mode,
        "custom_video_path": task.custom_video_path,
        "voice_profile_id": task.voice_profile_id,
        "avatar_profile_id": task.avatar_profile_id,
        "subtitle_style": task.subtitle_style,
        "background_music_path": task.background_music_path,
        "background_music_volume": task.background_music_volume,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def segment_to_dict(segment: ScriptSegmentModel) -> dict:
    """将文案段落 ORM 转为 API 段落字典。

    用途：
        段落列表、保存段落后的响应序列化。

    参数：
        segment: ScriptSegmentModel 实例。

    返回：
        含 index、时间轴、原文/编辑文、置信度等字段的 dict。

    逻辑：
        直接字段映射，不做业务变换。
    """
    return {
        "id": segment.id,
        "task_id": segment.task_id,
        "index": segment.index,
        "source_type": segment.source_type,
        "start_time": segment.start_time,
        "end_time": segment.end_time,
        "original_text": segment.original_text,
        "edited_text": segment.edited_text,
        "confidence": segment.confidence,
    }


def artifact_to_dict(artifact: ArtifactModel) -> dict:
    """将生成产物 ORM 转为 API 产物字典。

    用途：
        列出任务中间/最终产物（视频、音频、字幕等）。

    参数：
        artifact: ArtifactModel 实例。

    返回：
        含 type、path、meta、created_at 的 dict。

    逻辑：
        meta 保持 JSON 结构原样透出。
    """
    return {
        "id": artifact.id,
        "task_id": artifact.task_id,
        "type": artifact.type,
        "path": artifact.path,
        "meta": artifact.meta,
        "created_at": artifact.created_at,
    }


def finding_to_dict(finding: RiskFindingModel) -> dict:
    """将单条风险发现项 ORM 转为 API 字典。

    用途：
        嵌套在 risk_check_to_dict 的 findings 数组中。

    参数：
        finding: RiskFindingModel 实例。

    返回：
        含 type、target、text、position、suggestion 的 dict。

    逻辑：
        无聚合，单条映射。
    """
    return {
        "id": finding.id,
        "type": finding.type,
        "target": finding.target,
        "text": finding.text,
        "position": finding.position,
        "suggestion": finding.suggestion,
    }


def risk_check_to_dict(risk_check: RiskCheckModel) -> dict:
    """将风险审核记录 ORM 转为 API 字典（含 findings）。

    用途：
        风险列表、确认、发布前检查接口响应。

    参数：
        risk_check: 须已预加载 findings 关系的 RiskCheckModel。

    返回：
        含 stage、risk_status、risk_level、findings 列表等的 dict。

    逻辑：
        findings 通过 finding_to_dict 逐项转换。
    """
    return {
        "id": risk_check.id,
        "task_id": risk_check.task_id,
        "stage": risk_check.stage,
        "risk_status": risk_check.risk_status,
        "risk_level": risk_check.risk_level,
        "risk_types": risk_check.risk_types,
        "findings": [finding_to_dict(finding) for finding in risk_check.findings],
        "reviewed_by": risk_check.reviewed_by,
        "reviewed_at": risk_check.reviewed_at,
        "created_at": risk_check.created_at,
    }


def voice_profile_to_dict(voice: VoiceProfileModel) -> dict:
    """将音色档案 ORM 转为 API 字典。

    用途：
        生成配置页音色下拉列表。

    参数：
        voice: VoiceProfileModel 实例。

    返回：
        id、name、provider、sample_path、config 字段 dict。

    逻辑：
        config 为供应商相关 JSON 配置原样返回。
    """
    return {
        "id": voice.id,
        "name": voice.name,
        "provider": voice.provider,
        "sample_path": voice.sample_path,
        "config": voice.config,
    }


def avatar_profile_to_dict(avatar: AvatarProfileModel) -> dict:
    """将数字人形象档案 ORM 转为 API 字典。

    用途：
        生成配置页形象下拉列表。

    参数：
        avatar: AvatarProfileModel 实例。

    返回：
        id、name、provider、config 字段 dict。

    逻辑：
        不含 sample_path（形象配置在 config 内）。
    """
    return {"id": avatar.id, "name": avatar.name, "provider": avatar.provider, "config": avatar.config}


def distribution_to_dict(record: DistributionRecordModel) -> dict:
    """将分发记录 ORM 转为 API 字典。

    用途：
        分发列表、创建、重试接口响应。

    参数：
        record: DistributionRecordModel 实例。

    返回：
        含平台、标题、标签、状态、外链、错误信息、时间戳的 dict。

    逻辑：
        raw_result 不对外暴露，仅序列化业务可见字段。
    """
    return {
        "id": record.id,
        "task_id": record.task_id,
        "platform": record.platform,
        "title": record.title,
        "description": record.description,
        "tags": record.tags,
        "status": record.status,
        "external_url": record.external_url,
        "error_message": record.error_message,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
