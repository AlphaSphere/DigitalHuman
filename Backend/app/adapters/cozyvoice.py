"""CosyVoice 语音合成适配器（HTTP / Stub）。"""

import httpx

from app.core.config import get_settings
from app.services.storage_service import touch_file


class CozyVoiceAdapter:
    """CosyVoice TTS 服务适配器。

    外部服务：阿里 CosyVoice 语音合成模型，通常以独立 HTTP 服务部署，
    接收文本与音色参数，在服务端或指定路径写出 wav 文件。

    接入方式：
    - **HTTP**：生产环境，POST `{cozyvoice_base_url}/synthesize`。
    - **Stub**：`use_stub_model_adapters=true` 时写入占位 wav，便于无 GPU 联调。
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def synthesize(self, task_id: str, script: str, voice_profile_id: str | None, custom_voice_path: str | None) -> str:
        """将脚本文本合成为 TTS 音频文件。

        用途：
            在生成流水线「配音」阶段，把用户确认后的文案转为 wav，供 HeyGem 口型驱动使用。

        参数：
            task_id: 任务 ID，用于组织存储目录 `tasks/{task_id}/intermediate/`。
            script: 完整脚本文本（多段用换行拼接）。
            voice_profile_id: 预设音色 ID，可为 None。
            custom_voice_path: 用户上传的参考音色文件路径，可为 None。

        返回：
            生成的音频文件绝对路径（通常为 `tts_audio.wav`）。

        逻辑：
            1. Stub 模式：调用 touch_file 写入占位字节，立即返回路径。
            2. 计算预期输出路径 `intermediate/tts_audio.wav`。
            3. 向 CosyVoice HTTP 服务 POST JSON（含 text、音色、output_path）。
            4. 校验 HTTP 状态，解析响应中的 audio_path / path / output_path。
            5. 若未返回有效路径则抛出 ValueError。
        """
        if self.settings.use_stub_model_adapters:
            return touch_file(task_id, "intermediate/tts_audio.wav", b"stub tts audio")
        output_path = self.settings.storage_root / "tasks" / task_id / "intermediate" / "tts_audio.wav"
        with httpx.Client(timeout=self.settings.model_http_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.cozyvoice_base_url}/synthesize",
                json={
                    "task_id": task_id,
                    "text": script,
                    "script": script,
                    "voice_profile_id": voice_profile_id,
                    "custom_voice_path": custom_voice_path,
                    "output_path": str(output_path),
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"CosyVoice 服务调用失败: {_response_detail(response)}") from exc
            payload = response.json()
            audio_path = payload.get("audio_path") or payload.get("path") or payload.get("output_path")
            if not audio_path:
                raise ValueError("CosyVoice 未返回 audio_path")
            return audio_path


def _response_detail(response: httpx.Response) -> str:
    """从 HTTP 响应中提取可读错误详情，供异常信息展示。

    用途：
        统一解析 CosyVoice 返回的 JSON detail 或纯文本 body。

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
