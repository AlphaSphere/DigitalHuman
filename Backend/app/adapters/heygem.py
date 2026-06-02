"""HeyGem 数字人口型视频适配器（HTTP / Stub / 直通）。"""

import httpx

from app.core.config import get_settings
from app.domain.enums import GenerationVideoMode
from app.services.storage_service import touch_file


class HeyGemAdapter:
    """HeyGem 数字人视频生成适配器。

    外部服务：HeyGem 口型驱动服务，根据 TTS 音频与数字人形象生成对口型 mp4。
    用户若选择「上传自拍视频」模式，则跳过 HeyGem，直接使用 custom_video_path。

    接入方式：
    - **直通**：generation_video_mode=uploaded_video 且存在 custom_video_path 时原样返回。
    - **HTTP**：POST `{heygem_base_url}/generate`，传入 audio_path 与 avatar_profile_id。
    - **Stub**：`use_stub_model_adapters=true` 时写入占位 mp4。
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_avatar_video(
        self,
        task_id: str,
        audio_path: str,
        avatar_profile_id: str | None,
        generation_video_mode: str | None,
        custom_video_path: str | None,
    ) -> str:
        """生成数字人口播视频或使用用户上传视频。

        用途：
            生成流水线「数字人/口播视频」阶段，产出后续合成用的基础视频轨。

        参数：
            task_id: 任务 ID。
            audio_path: CozyVoice 生成的 TTS wav 路径（HeyGem 用于口型对齐）。
            avatar_profile_id: 预设数字人形象 ID。
            generation_video_mode: 生成模式枚举值（如 uploaded_video / avatar）。
            custom_video_path: 用户上传的自拍/口播视频路径。

        返回：
            基础视频 mp4 的绝对路径（HeyGem 输出或用户上传路径）。

        逻辑：
            1. 若为上传视频模式且 custom_video_path 存在，直接返回该路径（不调用 HeyGem）。
            2. Stub：写入占位 avatar_video.mp4。
            3. HTTP：POST generate 接口，传递 task_id、audio_path、avatar_profile_id、output_path。
            4. 解析响应中的 video_path / path / output_path，缺失则报错。
        """
        if generation_video_mode == GenerationVideoMode.uploaded_video.value and custom_video_path:
            return custom_video_path
        if self.settings.use_stub_model_adapters:
            return touch_file(task_id, "intermediate/avatar_video.mp4", b"stub avatar video")
        output_path = self.settings.storage_root / "tasks" / task_id / "intermediate" / "avatar_video.mp4"
        with httpx.Client(timeout=self.settings.model_http_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.heygem_base_url}/generate",
                json={
                    "task_id": task_id,
                    "audio_path": audio_path,
                    "avatar_profile_id": avatar_profile_id,
                    "output_path": str(output_path),
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"HeyGem 服务调用失败: {_response_detail(response)}") from exc
            payload = response.json()
            video_path = payload.get("video_path") or payload.get("path") or payload.get("output_path")
            if not video_path:
                raise ValueError("HeyGem 未返回 video_path")
            return video_path


def _response_detail(response: httpx.Response) -> str:
    """从 HTTP 响应中提取可读错误详情。

    用途：
        统一解析 HeyGem 返回的 JSON detail 或纯文本 body。

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
