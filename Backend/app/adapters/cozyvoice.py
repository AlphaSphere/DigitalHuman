"""CosyVoice 语音合成适配器（HTTP / Stub）。"""

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.domain.enums import GenerationQuality
from app.services.storage_service import touch_file

# 预设音色 SFT 可较长；克隆音色 cross_lingual 单段过长时 RTF 会飙到 10+（3～5 分钟/段）。
_TTS_CHUNK_MAX_CHARS = 180
_TTS_CHUNK_MAX_CHARS_CLONE = 60
_TTS_CHUNK_MAX_CHARS_CLONE_FAST = 40


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

    def synthesize(
        self,
        task_id: str,
        script: str,
        voice_profile_id: str | None,
        custom_voice_path: str | None,
        custom_voice_prompt_text: str | None = None,
        voice_speed: float | None = None,
        generation_quality: str | None = GenerationQuality.full.value,
    ) -> str:
        """将脚本文本合成为 TTS 音频文件。"""
        if self.settings.use_stub_model_adapters:
            return touch_file(task_id, "intermediate/tts_audio.wav", b"stub tts audio")

        output_path = self.settings.storage_root / "tasks" / task_id / "intermediate" / "tts_audio.wav"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        is_fast = generation_quality == GenerationQuality.fast.value
        if custom_voice_path:
            max_chars = _TTS_CHUNK_MAX_CHARS_CLONE_FAST if is_fast else _TTS_CHUNK_MAX_CHARS_CLONE
        else:
            max_chars = _TTS_CHUNK_MAX_CHARS
        chunks = _split_tts_chunks(script, max_chars=max_chars)

        with httpx.Client(timeout=self.settings.model_http_timeout_seconds, trust_env=False) as client:
            if len(chunks) <= 1:
                return self._synthesize_once(
                    client,
                    task_id=task_id,
                    text=chunks[0] if chunks else script,
                    voice_profile_id=voice_profile_id,
                    custom_voice_path=custom_voice_path,
                    custom_voice_prompt_text=custom_voice_prompt_text,
                    voice_speed=voice_speed,
                    output_path=output_path,
                )

            max_workers = 3 if is_fast and custom_voice_path else 2 if custom_voice_path else 1
            part_paths: list[Path | None] = [None] * len(chunks)

            def _run_chunk(index: int, chunk: str) -> tuple[int, Path]:
                part_path = output_path.parent / f"tts_part_{index:04d}.wav"
                self._synthesize_once(
                    client,
                    task_id=task_id,
                    text=chunk,
                    voice_profile_id=voice_profile_id,
                    custom_voice_path=custom_voice_path,
                    custom_voice_prompt_text=custom_voice_prompt_text,
                    voice_speed=voice_speed,
                    output_path=part_path,
                )
                return index, part_path

            if max_workers <= 1:
                for index, chunk in enumerate(chunks):
                    _, part_path = _run_chunk(index, chunk)
                    part_paths[index] = part_path
            else:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(_run_chunk, index, chunk) for index, chunk in enumerate(chunks)]
                    for future in as_completed(futures):
                        index, part_path = future.result()
                        part_paths[index] = part_path

            ordered_parts = [path for path in part_paths if path is not None]
            _concat_wav_files(ordered_parts, output_path, self.settings.ffmpeg_command)
            return str(output_path)

    def _synthesize_once(
        self,
        client: httpx.Client,
        *,
        task_id: str,
        text: str,
        voice_profile_id: str | None,
        custom_voice_path: str | None,
        custom_voice_prompt_text: str | None,
        voice_speed: float | None,
        output_path: Path,
    ) -> str:
        """调用 8002 合成单段文本并写入 output_path。"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = client.post(
                f"{self.settings.cozyvoice_base_url}/synthesize",
                json={
                    "task_id": task_id,
                    "text": text,
                    "script": text,
                    "voice_profile_id": voice_profile_id,
                    "custom_voice_path": custom_voice_path,
                    "custom_voice_prompt_text": custom_voice_prompt_text,
                    "output_path": str(output_path),
                    "speed": voice_speed or 1.0,
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            response = exc.response
            raise RuntimeError(f"CosyVoice 服务调用失败: {_response_detail(response)}") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"CosyVoice 配音超时（>{int(self.settings.model_http_timeout_seconds)}s）。"
                "若文案较长，请稍后重试；仍失败请重启 CosyVoice 上游 :50000。"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"CosyVoice 服务不可达（{self.settings.cozyvoice_base_url}）：{exc}。"
                "请重启一键启动脚本以拉起 8002 端口服务，或在 .env 中配置 COSYVOICE_UPSTREAM_URL 接入真实 CosyVoice。"
            ) from exc

        payload = response.json()
        audio_path = payload.get("audio_path") or payload.get("path") or payload.get("output_path")
        if not audio_path:
            raise ValueError("CosyVoice 未返回 audio_path")
        return audio_path


def _split_tts_chunks(text: str, max_chars: int = _TTS_CHUNK_MAX_CHARS) -> list[str]:
    """按自然停顿切分长文案，避免克隆音色单段过长导致 RTF 飙升。"""
    normalized = _normalize_tts_text(text)
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]

    parts = re.split(r"(?<=[。！？；.!?，,、\n])", normalized)
    chunks: list[str] = []
    buffer = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if len(piece) > max_chars:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            for offset in range(0, len(piece), max_chars):
                chunks.append(piece[offset : offset + max_chars])
            continue
        if len(buffer) + len(piece) <= max_chars:
            buffer += piece
        else:
            if buffer:
                chunks.append(buffer)
            buffer = piece
    if buffer:
        chunks.append(buffer)
    return chunks


def _normalize_tts_text(text: str) -> str:
    """清理 TTS 文本中的重复空白和过量标点，降低推理异常与拖慢概率。"""
    normalized = re.sub(r"\s+", "，", text.strip())
    normalized = re.sub(r"[，,、]{2,}", "，", normalized)
    normalized = re.sub(r"。{2,}", "。", normalized)
    normalized = re.sub(r"[！？!?]{2,}", "！", normalized)
    return normalized.strip("，,、 \n\t")


def _concat_wav_files(part_paths: list[Path], output_path: Path, ffmpeg_command: str) -> None:
    """用 ffmpeg concat demuxer 拼接多段 WAV。"""
    list_path = output_path.parent / "tts_concat_list.txt"
    list_path.write_text(
        "\n".join(f"file '{path.resolve().as_posix()}'" for path in part_paths),
        encoding="utf-8",
    )
    try:
        subprocess.run(
            [
                ffmpeg_command,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"配音分段拼接失败: {(exc.stderr or exc.stdout)[-500:]}") from exc
    finally:
        list_path.unlink(missing_ok=True)


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
        detail = payload.get("detail") or payload
        text = str(detail).strip()
        if text:
            return text
    except ValueError:
        pass
    text = (response.text or "").strip()
    if text:
        return text[:500]
    return f"HTTP {response.status_code}，无响应正文"
