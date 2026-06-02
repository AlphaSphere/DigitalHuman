"""HeyGem 数字人视频生成微服务入口。

用途：封装多种视频合成方式（官方 Video API、HTTP 上游、Shell 命令），
将配音音频与数字人/参考视频合成为口播视频。
"""

import json
import shlex
import shutil
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """HeyGem 服务运行配置，从环境变量与 .env 文件加载。

    用途：控制上游地址、官方 Video API、命令模板、头像映射与轮询超时等参数。
    """

    heygem_upstream_url: str | None = None
    heygem_video_base_url: str | None = None
    heygem_command_template: str | None = None
    heygem_default_video_path: str | None = None
    heygem_avatar_profile_map: str | None = None
    heygem_result_dir: Path | None = None
    heygem_poll_interval_seconds: float = 5
    heygem_poll_timeout_seconds: float = 1800
    heygem_workdir: Path | None = None
    heygem_timeout_seconds: float = 1800
    allow_stub_output: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator(
        "heygem_upstream_url",
        "heygem_video_base_url",
        "heygem_command_template",
        "heygem_default_video_path",
        "heygem_avatar_profile_map",
        "heygem_result_dir",
        "heygem_workdir",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value):
        """将空字符串规范化为 None。

        用途：允许通过空环境变量表示「未配置该项」。

        参数:
            value: 原始配置值。

        返回:
            非空字符串原样返回，空字符串转为 None。

        逻辑:
            在 Pydantic 校验前执行，便于下游分支判断使用哪种生成模式。
        """
        return None if value == "" else value


class GenerateRequest(BaseModel):
    """数字人视频生成请求体。

    用途：描述任务 ID、配音音频路径、数字人配置与输出路径。
    """

    task_id: str = Field(..., min_length=1)
    audio_path: str = Field(..., min_length=1)
    avatar_profile_id: str | None = None
    output_path: str = Field(..., min_length=1)


class GenerateResponse(BaseModel):
    """数字人视频生成响应体。

    用途：返回生成视频在存储中的路径。
    """

    video_path: str


settings = Settings()
app = FastAPI(title="DigitalHuman HeyGem Service")


@app.get("/health")
def health() -> dict:
    """健康检查端点。

    用途：供编排系统探测服务状态及当前生成模式。

    返回:
        包含 status、service 名称与 mode 的字典。

    逻辑:
        按配置优先级推断 official-video-api / upstream-http / command / unconfigured。
    """
    mode = "official-video-api" if settings.heygem_video_base_url else "upstream-http"
    if not settings.heygem_video_base_url and not settings.heygem_upstream_url:
        mode = "command"
    if not settings.heygem_video_base_url and not settings.heygem_upstream_url and not settings.heygem_command_template:
        mode = "unconfigured"
    return {"status": "ok", "service": "heygem", "mode": mode}


@app.post("/generate", response_model=GenerateResponse)
def generate(payload: GenerateRequest) -> GenerateResponse:
    """将配音音频与数字人素材合成为口播视频。

    用途：主业务入口，按配置自动选择官方 API/上游/命令/stub 生成方式。

    参数:
        payload: 包含音频路径、头像配置与输出路径的生成请求。

    返回:
        含 video_path 的 GenerateResponse。

    逻辑:
        1. 校验音频文件存在并创建输出目录；
        2. 按 official_video → upstream → command → stub 优先级路由；
        3. 均未配置且未允许 stub 时返回 503。
    """
    audio_path = Path(payload.audio_path)
    if not audio_path.exists():
        raise HTTPException(status_code=400, detail=f"配音音频不存在: {payload.audio_path}")

    output_path = Path(payload.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.heygem_video_base_url:
        return _generate_official_video(payload, output_path)
    if settings.heygem_upstream_url:
        return _generate_upstream(payload)
    if settings.heygem_command_template:
        return _generate_command(payload, output_path)
    if settings.allow_stub_output:
        # 仅供本地联调协议使用；真实生成时必须关闭并配置 HeyGem 仓库命令或上游服务。
        output_path.write_bytes(b"stub heygem video")
        return GenerateResponse(video_path=str(output_path))
    raise HTTPException(status_code=503, detail="HeyGem 服务未配置：请设置 HEYGEM_COMMAND_TEMPLATE 或 HEYGEM_UPSTREAM_URL")


def _generate_upstream(payload: GenerateRequest) -> GenerateResponse:
    """通过 HTTP 上游服务执行视频生成。

    用途：将生成请求转发至外部 HeyGem 或 DigitalHuman 兼容上游。

    参数:
        payload: 生成请求体。

    返回:
        上游返回的 video_path 封装为 GenerateResponse。

    逻辑:
        POST JSON 到 /generate，从响应中解析 video_path/path/output_path 字段。
    """
    assert settings.heygem_upstream_url
    try:
        with httpx.Client(timeout=settings.heygem_timeout_seconds) as client:
            response = client.post(f"{settings.heygem_upstream_url.rstrip('/')}/generate", json=payload.model_dump())
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HeyGem 上游调用失败: {exc}") from exc
    video_path = data.get("video_path") or data.get("path") or data.get("output_path")
    if not video_path:
        raise HTTPException(status_code=502, detail="HeyGem 上游未返回 video_path")
    return GenerateResponse(video_path=video_path)


def _generate_official_video(payload: GenerateRequest, output_path: Path) -> GenerateResponse:
    """调用 HeyGem 官方 Video API 提交并轮询合成任务。

    用途：对接 /easy/submit 与 /easy/query 异步视频合成流程。

    参数:
        payload: 生成请求体。
        output_path: 期望的最终视频输出路径。

    返回:
        解析并复制视频到 output_path 后的 GenerateResponse。

    逻辑:
        1. 解析 avatar 参考视频路径；
        2. 提交任务并轮询直至完成或失败；
        3. 从 query/submit 响应或结果目录查找视频；
        4. 复制到 output_path 或返回远程路径。
    """
    video_path = _resolve_avatar_video_path(payload.avatar_profile_id)
    if not video_path:
        raise HTTPException(
            status_code=400,
            detail="HeyGem 官方视频合成需要 avatar_profile_id 指向视频路径，或配置 HEYGEM_DEFAULT_VIDEO_PATH",
        )

    task_code = uuid4().hex
    submit_payload = {
        "audio_url": payload.audio_path,
        "video_url": video_path,
        "code": task_code,
        "chaofen": 0,
        "watermark_switch": 0,
        "pn": 1,
    }
    try:
        with httpx.Client(timeout=settings.heygem_timeout_seconds) as client:
            submit_response = client.post(
                f"{settings.heygem_video_base_url.rstrip('/')}/easy/submit",
                json=submit_payload,
            )
            submit_response.raise_for_status()
            submit_data = _json_or_text(submit_response)
            query_data = _poll_official_video(client, task_code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HeyGem 官方视频合成调用失败: {exc}") from exc

    resolved = _extract_video_path(query_data) or _extract_video_path(submit_data) or _find_result_file(task_code)
    if not resolved:
        raise HTTPException(status_code=502, detail=f"HeyGem 合成完成但未找到输出视频: {query_data}")
    return GenerateResponse(video_path=_copy_or_return_video(resolved, output_path))


def _poll_official_video(client: httpx.Client, task_code: str):
    """轮询官方 Video API 直至任务完成、失败或超时。

    用途：异步合成提交后等待最终结果。

    参数:
        client: 复用的 httpx 客户端。
        task_code: 提交时生成的任务唯一标识。

    返回:
        任务完成时的 query 响应 payload。

    逻辑:
        在 poll_timeout 内按 poll_interval 调用 /easy/query；
        检测到失败标记抛 RuntimeError，成功标记返回 payload，超时抛 TimeoutError。
    """
    deadline = time.monotonic() + settings.heygem_poll_timeout_seconds
    last_payload = None
    while time.monotonic() < deadline:
        response = client.get(f"{settings.heygem_video_base_url.rstrip('/')}/easy/query", params={"code": task_code})
        response.raise_for_status()
        payload = _json_or_text(response)
        last_payload = payload
        if _is_failed(payload):
            raise RuntimeError(f"HeyGem 任务失败: {payload}")
        if _is_finished(payload):
            return payload
        time.sleep(settings.heygem_poll_interval_seconds)
    raise TimeoutError(f"HeyGem 任务超时，最后状态: {last_payload}")


def _resolve_avatar_video_path(avatar_profile_id: str | None) -> str | None:
    """解析数字人参考视频的实际路径。

    用途：将 avatar_profile_id 映射为 HeyGem 可用的 video_url。

    参数:
        avatar_profile_id: 头像配置 ID 或直接视频路径。

    返回:
        存在的视频路径字符串，无法解析时返回 None。

    逻辑:
        依次尝试：ID 本身是否为现有文件 → 配置映射表 → 默认视频路径。
    """
    if avatar_profile_id and Path(avatar_profile_id).exists():
        return avatar_profile_id
    mapped_path = _avatar_profile_map().get(avatar_profile_id or "")
    if mapped_path and Path(mapped_path).exists():
        return mapped_path
    if settings.heygem_default_video_path and Path(settings.heygem_default_video_path).exists():
        return settings.heygem_default_video_path
    return None


def _avatar_profile_map() -> dict[str, str]:
    """解析 HEYGEM_AVATAR_PROFILE_MAP 环境变量为 ID→路径字典。

    用途：将逻辑 avatar ID 映射到本地或共享存储中的参考视频。

    返回:
        字符串键值对映射表，未配置时返回空 dict。

    逻辑:
        JSON 解析失败或非 dict 类型时抛 HTTPException 500。
    """
    if not settings.heygem_avatar_profile_map:
        return {}
    try:
        value = json.loads(settings.heygem_avatar_profile_map)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"HEYGEM_AVATAR_PROFILE_MAP 不是合法 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=500, detail="HEYGEM_AVATAR_PROFILE_MAP 必须是对象，例如 {\"avatar_studio_a\":\"/path/a.mp4\"}")
    return {str(key): str(path) for key, path in value.items()}


def _generate_command(payload: GenerateRequest, output_path: Path) -> GenerateResponse:
    """通过 Shell 命令模板调用外部 HeyGem 脚本。

    用途：对接官方仓库 CLI 或自定义视频生成脚本。

    参数:
        payload: 生成请求体。
        output_path: 视频输出路径。

    返回:
        命令成功且文件存在时的 GenerateResponse。

    逻辑:
        format 命令模板并 subprocess.run，校验 output_path 是否生成。
    """
    values = {
        "task_id": payload.task_id,
        "audio_path": payload.audio_path,
        "output_path": str(output_path),
        "avatar_profile_id": payload.avatar_profile_id or "",
    }
    command = settings.heygem_command_template.format(**values)
    try:
        subprocess.run(
            shlex.split(command),
            cwd=str(settings.heygem_workdir) if settings.heygem_workdir else None,
            check=True,
            capture_output=True,
            text=True,
            timeout=settings.heygem_timeout_seconds,
        )
    except subprocess.CalledProcessError as exc:
        message = exc.stderr or exc.stdout or str(exc)
        raise HTTPException(status_code=500, detail=f"HeyGem 命令执行失败: {message}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HeyGem 命令启动失败: {exc}") from exc
    if not output_path.exists():
        raise HTTPException(status_code=500, detail=f"HeyGem 命令未生成视频: {output_path}")
    return GenerateResponse(video_path=str(output_path))


def _json_or_text(response: httpx.Response):
    """尝试将 HTTP 响应解析为 JSON，失败则包装为 text 字段。

    用途：兼容官方 API 可能返回非 JSON 的错误体。

    参数:
        response: httpx 响应对象。

    返回:
        解析后的 dict 或 {"text": response.text}。
    """
    try:
        return response.json()
    except ValueError:
        return {"text": response.text}


def _is_finished(payload) -> bool:
    """判断 HeyGem 任务响应是否表示已完成。

    用途：轮询时识别成功终态。

    参数:
        payload: 任意嵌套的 API 响应结构。

    返回:
        扁平化值中包含成功标记时为 True。

    逻辑:
        递归展平 payload，匹配 success/succeeded/completed 等标记。
    """
    values = _flatten_values(payload)
    success_markers = {"success", "succeeded", "complete", "completed", "finish", "finished", "done", "2", 2}
    return any(value in success_markers for value in values)


def _is_failed(payload) -> bool:
    """判断 HeyGem 任务响应是否表示已失败。

    用途：轮询时识别失败终态并提前终止。

    参数:
        payload: 任意嵌套的 API 响应结构。

    返回:
        扁平化值中包含失败标记时为 True。
    """
    values = _flatten_values(payload)
    failed_markers = {"fail", "failed", "error", "exception", "-1", -1}
    return any(value in failed_markers for value in values)


def _flatten_values(payload) -> list:
    """递归展平嵌套结构为叶子值列表。

    用途：供 _is_finished/_is_failed 在未知 JSON 结构中搜索状态标记。

    参数:
        payload: dict、list、str 或其他标量。

    返回:
        叶子值列表；字符串转为小写。

    逻辑:
        Mapping/list 递归展开；字符串 lower；标量直接 append。
    """
    if isinstance(payload, Mapping):
        values = []
        for value in payload.values():
            values.extend(_flatten_values(value))
        return values
    if isinstance(payload, list):
        values = []
        for item in payload:
            values.extend(_flatten_values(item))
        return values
    if isinstance(payload, str):
        return [payload.lower()]
    return [payload]


def _extract_video_path(payload) -> str | None:
    """从嵌套 API 响应中提取视频路径或 URL。

    用途：兼容多种上游字段命名与嵌套层级。

    参数:
        payload: 任意 JSON 可序列化结构。

    返回:
        首个看起来像视频文件的路径/URL，未找到返回 None。

    逻辑:
        优先匹配 video_path/video_url 等键；递归搜索子结构；字符串直接校验后缀。
    """
    if isinstance(payload, Mapping):
        for key in ("video_path", "video_url", "output_path", "result_path", "path", "url"):
            value = payload.get(key)
            if isinstance(value, str) and _looks_like_video(value):
                return value
        for value in payload.values():
            found = _extract_video_path(value)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _extract_video_path(item)
            if found:
                return found
    if isinstance(payload, str) and _looks_like_video(payload):
        return payload
    return None


def _looks_like_video(value: str) -> bool:
    """判断字符串是否像视频文件路径或 URL。

    用途：过滤 _extract_video_path 中的候选值。

    参数:
        value: 待检测字符串。

    返回:
        以常见视频扩展名结尾时为 True。
    """
    return value.lower().endswith((".mp4", ".mov", ".mkv", ".avi"))


def _find_result_file(task_code: str) -> str | None:
    """在结果目录中按 task_code 搜索最新生成的 mp4 文件。

    用途：官方 API 未在 JSON 中返回路径时的兜底查找。

    参数:
        task_code: 任务唯一标识。

    返回:
        最新匹配 mp4 的路径字符串，未找到返回 None。
    """
    if not settings.heygem_result_dir or not settings.heygem_result_dir.exists():
        return None
    candidates = sorted(
        settings.heygem_result_dir.rglob(f"*{task_code}*.mp4"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return str(candidates[0]) if candidates else None


def _copy_or_return_video(source: str, output_path: Path) -> str:
    """将源视频复制到期望输出路径，或返回不可复制的远程路径。

    用途：统一官方 API 返回路径与任务存储目录的落盘行为。

    参数:
        source: 源视频路径或 URL。
        output_path: 期望的最终输出路径。

    返回:
        本地复制后为 output_path 字符串；源不存在则原样返回 source。

    逻辑:
        源文件存在且与 output_path 不同时 shutil.copyfile；否则返回 source 供调用方处理。
    """
    source_path = Path(source)
    if source_path.exists():
        if source_path.resolve() != output_path.resolve():
            shutil.copyfile(source_path, output_path)
        return str(output_path)
    return source
