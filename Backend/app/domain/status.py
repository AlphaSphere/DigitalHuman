from app.domain.enums import TaskStatus


STATUS_MESSAGES: dict[TaskStatus, str] = {
    TaskStatus.uploaded: "视频已上传，等待识别",
    TaskStatus.audio_extracted: "音频提取完成",
    TaskStatus.transcribing: "正在识别文案",
    TaskStatus.transcribed: "文案识别完成，请确认",
    TaskStatus.script_pasted: "文案已提交，等待解析",
    TaskStatus.script_parsing: "正在解析文案",
    TaskStatus.script_parsed: "文案解析完成，请确认",
    TaskStatus.script_confirmed: "文案已确认，可以配置生成参数",
    TaskStatus.content_checking: "正在检查内容风险",
    TaskStatus.content_review_required: "内容需要人工确认",
    TaskStatus.content_rejected: "内容风险较高，请修改",
    TaskStatus.dubbing: "正在生成配音",
    TaskStatus.dubbed: "配音生成完成",
    TaskStatus.avatar_generating: "正在生成数字人口播视频",
    TaskStatus.avatar_generated: "数字人视频生成完成",
    TaskStatus.subtitle_generating: "正在生成字幕",
    TaskStatus.composing: "正在合成最终视频",
    TaskStatus.publish_checking: "正在进行发布前合规检查",
    TaskStatus.publish_blocked: "发布前检查未通过",
    TaskStatus.publish_ready: "已通过发布前检查",
    TaskStatus.completed: "成片已生成",
    TaskStatus.failed: "生成失败，可查看原因并重试",
    TaskStatus.retrying: "正在从失败节点重试",
}

PROGRESS_ORDER = [
    TaskStatus.uploaded,
    TaskStatus.transcribing,
    TaskStatus.transcribed,
    TaskStatus.script_confirmed,
    TaskStatus.content_checking,
    TaskStatus.content_review_required,
    TaskStatus.dubbing,
    TaskStatus.dubbed,
    TaskStatus.avatar_generating,
    TaskStatus.avatar_generated,
    TaskStatus.subtitle_generating,
    TaskStatus.composing,
    TaskStatus.completed,
]


def build_progress(status: TaskStatus) -> dict:
    if status == TaskStatus.failed:
        return {"stage": status, "percent": 0, "message": STATUS_MESSAGES[status]}
    index = PROGRESS_ORDER.index(status) if status in PROGRESS_ORDER else 0
    percent = min(100, round(index / (len(PROGRESS_ORDER) - 1) * 100))
    return {"stage": status, "percent": percent, "message": STATUS_MESSAGES[status]}
