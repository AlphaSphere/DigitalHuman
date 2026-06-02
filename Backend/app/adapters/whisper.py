"""OpenAI Whisper 语音识别适配器（HTTP / CLI / Stub）。"""

import json
import subprocess
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.services.script_parser import DEFAULT_SCRIPT
from app.services.storage_service import task_dir


class WhisperAdapter:
    """Whisper ASR 适配器。

    外部服务：OpenAI Whisper 模型，将音频转写为带时间戳的文本分段。
    支持远程 HTTP 服务与本地 whisper CLI 两种方式，由配置自动选择。

    接入方式：
    - **Stub**：`use_stub_model_adapters=true` 时返回固定 DEFAULT_SCRIPT 分段。
    - **HTTP**：配置了 `whisper_base_url` 时 POST `/transcribe`（适合 GPU 服务化部署）。
    - **CLI**：未配置 base_url 时调用本地 `whisper_command`，输出 JSON 到任务 intermediate 目录。
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def transcribe(self, source_video_path: str | None, task_id: str | None = None) -> list[dict]:
        """转写音频/视频中的语音为分段文案。

        用途：
            上传视频后的「转写」Worker 任务，产出 ScriptSegment 入库前的原始分段。

        参数：
            source_video_path: 待识别文件路径（通常为 extract_audio 后的 wav，或视频路径）。
            task_id: 任务 ID；CLI 模式用于确定 JSON 输出目录，可为 None（使用 manual 目录）。

        返回：
            分段列表，每项含 start_time、end_time、text、confidence（可选）。

        逻辑：
            1. Stub：返回单段默认文案。
            2. 校验 source_video_path 非空。
            3. 若配置了 whisper_base_url → HTTP 转写。
            4. 否则 → 本地 CLI 转写并读取 JSON。
        """
        if self.settings.use_stub_model_adapters:
            return [{"start_time": 0, "end_time": 6, "text": DEFAULT_SCRIPT, "confidence": 0.92}]
        if not source_video_path:
            raise ValueError("Whisper 识别需要 source_video_path")
        if self.settings.whisper_base_url:
            return self._transcribe_http(source_video_path)
        return self._transcribe_cli(source_video_path, task_id)

    def _transcribe_http(self, source_video_path: str) -> list[dict]:
        """通过 Whisper HTTP 微服务转写。

        用途：
            生产环境推荐：Whisper 跑在独立 GPU 容器，Backend Worker 只发 HTTP 请求。

        参数：
            source_video_path: 服务端可访问的文件路径。

        返回：
            经 _normalize_segments 统一格式后的分段列表。

        逻辑：
            1. POST transcribe 接口，携带 path、language、model。
            2. 校验状态码，解析 segments 字段。
            3. 归一化字段名（start/end → start_time/end_time）。
        """
        with httpx.Client(timeout=self.settings.model_http_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.whisper_base_url}/transcribe",
                json={
                    "path": source_video_path,
                    "language": self.settings.whisper_language,
                    "model": self.settings.whisper_model,
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"Whisper 服务调用失败: {_response_detail(response)}") from exc
            payload = response.json()
            return self._normalize_segments(payload.get("segments", payload))

    def _transcribe_cli(self, source_video_path: str, task_id: str | None) -> list[dict]:
        """通过本地 whisper 命令行转写。

        用途：
            开发或小规模部署：Worker 镜像内安装 openai-whisper，直接 subprocess 调用。

        参数：
            source_video_path: 本地音频/视频路径。
            task_id: 输出 JSON 写入 `tasks/{task_id}/intermediate/`。

        返回：
            归一化后的分段列表。

        逻辑：
            1. 在 intermediate 目录执行 whisper，指定 model 与 json 输出格式。
            2. 读取 `{stem}.json`，解析 segments。
            3. 归一化并返回。
        """
        output_dir = task_dir(task_id or "manual") / "intermediate"
        subprocess.run(
            [
                self.settings.whisper_command,
                source_video_path,
                "--model",
                self.settings.whisper_model,
                "--output_format",
                "json",
                "--output_dir",
                str(output_dir),
            ],
            check=True,
        )
        json_path = output_dir / f"{Path(source_video_path).stem}.json"
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        return self._normalize_segments(payload.get("segments", []))

    def _normalize_segments(self, segments: list[dict]) -> list[dict]:
        """将 HTTP/CLI 各异的分段结构统一为内部格式。

        用途：
            兼容 Whisper API、CLI JSON 中不同的字段命名（start vs start_time 等）。

        参数：
            segments: 原始分段 dict 列表。

        返回：
            统一含 start_time、end_time、text、confidence 的列表；空结果抛 ValueError。

        逻辑：
            1. 遍历分段，提取 text/sentence，跳过空文本。
            2. 映射时间字段，缺省则按 index 估算 4 秒间隔。
            3. 若最终无有效分段，抛出「未返回可用文案」。
        """
        normalized = []
        for index, segment in enumerate(segments):
            text = segment.get("text") or segment.get("sentence") or ""
            if text.strip():
                normalized.append(
                    {
                        "start_time": float(segment.get("start", segment.get("start_time", index * 4))),
                        "end_time": float(segment.get("end", segment.get("end_time", index * 4 + 3.6))),
                        "text": text.strip(),
                        "confidence": segment.get("confidence"),
                    }
                )
        if not normalized:
            raise ValueError("Whisper 未返回可用文案")
        return normalized


def _response_detail(response: httpx.Response) -> str:
    """从 HTTP 响应中提取可读错误详情。

    参数：
        response: httpx 响应对象。

    返回：
        错误描述字符串。
    """
    try:
        payload = response.json()
    except ValueError:
        return response.text
    return str(payload.get("detail") or payload)
