"""Ultralight-Digital-Human ONNX 本地推理（基于 dihuman_run.py）。"""

from __future__ import annotations

import importlib.util
import math
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import cv2
import numpy as np
import onnxruntime
import soundfile as sf


SAMPLE_RATE = 16000
FRAME_LEN = 160


def _load_dihuman_processor(
    repo_path: Path,
    data_path: Path,
    execution_provider: str,
    *,
    compress_inference: bool = False,
):
    """从 Ultralight 仓库加载 DiHumanProcessor，并注入 ONNX 执行提供者。"""
    module_path = repo_path / "dihuman_run.py"
    if not module_path.exists():
        raise FileNotFoundError(f"未找到推理脚本: {module_path}")

    spec = importlib.util.spec_from_file_location("dihuman_run", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["dihuman_run"] = module
    spec.loader.exec_module(module)

    providers = _resolve_providers(execution_provider)
    original_init = module.DiHumanProcessor.__init__

    def patched_init(self, data_path_arg: str):
        self.full_body_img_dir = os.path.join(data_path_arg, "img_inference")
        self.lms_dir = os.path.join(data_path_arg, "lms_inference")

        self.full_body_img_list = []
        self.bbox_list = []
        n_frames = len(os.listdir(self.lms_dir)) - 1
        for i in range(n_frames):
            img = cv2.imread(os.path.join(self.full_body_img_dir, f"{i}.jpg"))
            self.full_body_img_list.append(img)
            bbox = module._read_landmarks_to_bbox(os.path.join(self.lms_dir, f"{i}.lms"))
            self.bbox_list.append(bbox)

        self.offset = np.ones((1,), dtype=np.int64) * 100
        self.att_cache = np.zeros([3, 8, 16, 128], dtype=np.float32)
        self.cnn_cache = np.zeros([3, 1, 512, 14], dtype=np.float32)

        self.ort_unet = onnxruntime.InferenceSession(
            os.path.join(data_path_arg, "unet.onnx"),
            providers=providers,
        )
        self.ort_ae = onnxruntime.InferenceSession(
            os.path.join(data_path_arg, "encoder.onnx"),
            providers=providers,
        )

        self.frame_picker = module._BounceIndex(len(self.bbox_list))
        self.audio_play_list = [0] * module.PLAY_PRE_PAD
        self.audio_queue_get_feat = np.zeros([module.PRE_AUDIO_LEN], dtype=np.int16)
        self.using_feat = np.zeros([module.USING_FEAT_INIT, 16, 512], dtype=np.float32)

        self.counter = 0
        self.empty_audio_counter = 56
        self.is_processing = False
        self.silence = True

    module.DiHumanProcessor.__init__ = patched_init
    if compress_inference:
        # 快速模式：减少静音占位帧输出频率，降低无效逐帧开销
        idle_loop = getattr(module, "IDLE_LOOP", 5)
        module.IDLE_LOOP = max(2, idle_loop * 2)
    return module.DiHumanProcessor(str(data_path))


def _resolve_providers(execution_provider: str) -> list[str]:
    """按配置选择 CUDA/CPU 执行提供者。"""
    available = onnxruntime.get_available_providers()
    prefer_cuda = execution_provider.lower() in {"cuda", "gpu", "auto"}
    if prefer_cuda and "CUDAExecutionProvider" in available:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def _ensure_avatar_ready(data_path: Path) -> None:
    """校验数字人素材目录结构。"""
    required = [
        data_path / "img_inference",
        data_path / "lms_inference",
        data_path / "unet.onnx",
        data_path / "encoder.onnx",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "TuiliONNX 数字人素材不完整，缺少: "
            + ", ".join(missing)
            + "。请运行 python scripts/windows/setup_tuilionnx.py prepare --video 你的口播视频.mp4"
        )


def _read_audio_int16(audio_path: Path) -> np.ndarray:
    """读取音频并转为 16kHz 单声道 int16。"""
    stream, sample_rate = sf.read(str(audio_path))
    if stream.ndim == 2:
        stream = stream[:, 0]
    stream = stream.astype(np.float32)
    if sample_rate != SAMPLE_RATE:
        import librosa

        stream = librosa.resample(stream, orig_sr=sample_rate, target_sr=SAMPLE_RATE)
    return (stream * 32767).astype(np.int16)


def _probe_first_image_size(data_path: Path) -> tuple[int, int]:
    img_dir = data_path / "img_inference"
    first = sorted(img_dir.glob("*.jpg"))[0]
    img = cv2.imread(str(first))
    if img is None:
        raise RuntimeError(f"无法读取素材图片: {first}")
    height, width = img.shape[:2]
    return width, height


def _apply_sync_offset(audio: np.ndarray, sync_offset: int) -> np.ndarray:
    """按帧偏移微调口型音频对齐（正值延后，负值提前）。"""
    if sync_offset == 0:
        return audio
    shift_samples = sync_offset * FRAME_LEN
    if shift_samples > 0:
        return np.concatenate([np.zeros(shift_samples, dtype=np.int16), audio])
    trim = min(audio.shape[0], abs(shift_samples))
    return audio[trim:]


def render_avatar_video(
    *,
    repo_path: Path,
    data_path: Path,
    audio_path: Path,
    output_path: Path,
    execution_provider: str = "auto",
    compress_inference: bool = False,
    sync_offset: int = 0,
    inference_scale: float = 1.0,
) -> tuple[Path, Path]:
    """用 ONNX 流式推理生成口播视频，并用与口型对齐的音频合并。

    DiHumanProcessor 内部有 PLAY_PRE_PAD 等延迟补偿，必须使用 process() 返回的
    playing_audio 合并，不能直接贴原始 TTS，否则口型会整体提前或滞后。
    """
    _ensure_avatar_ready(data_path)
    repo_path = repo_path.resolve()
    data_path = data_path.resolve()
    audio_path = audio_path.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    processor_cls = _load_dihuman_processor(
        repo_path,
        data_path,
        execution_provider,
        compress_inference=compress_inference,
    )
    processor = processor_cls(str(data_path))

    stream = _read_audio_int16(audio_path)
    width, height = _probe_first_image_size(data_path)
    if inference_scale < 1.0:
        width = max(2, int(width * inference_scale) // 2 * 2)
        height = max(2, int(height * inference_scale) // 2 * 2)
    temp_video = output_path.with_suffix(".onnx_temp.mp4")
    writer = cv2.VideoWriter(
        str(temp_video),
        cv2.VideoWriter_fourcc(*"mp4v"),
        20,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError("OpenCV 无法创建临时视频文件，请确认已安装 opencv-python")

    synced_audio_path = output_path.with_name("avatar_synced_audio.wav")
    audio_out: list[np.ndarray] = []
    try:
        n_chunks = math.ceil(stream.shape[0] / FRAME_LEN)
        for index in range(n_chunks):
            start = index * FRAME_LEN
            end = min(start + FRAME_LEN, stream.shape[0])
            audio_frame = stream[start:end]
            img, playing_audio, check_img = processor.process(audio_frame)
            audio_out.append(playing_audio)
            if check_img and img is not None:
                if img.shape[1] != width or img.shape[0] != height:
                    img = cv2.resize(img, (width, height))
                writer.write(img)
    finally:
        writer.release()

    if not temp_video.exists() or temp_video.stat().st_size == 0:
        raise RuntimeError("ONNX 推理未生成任何视频帧，请检查数字人素材与音频")

    synced_audio = _apply_sync_offset(np.concatenate(audio_out).astype(np.int16), sync_offset)
    sf.write(
        str(synced_audio_path),
        synced_audio.astype(np.float32) / 32767.0,
        SAMPLE_RATE,
        subtype="PCM_16",
    )

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        temp_video.replace(output_path)
        return output_path, synced_audio_path

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(temp_video),
        "-i",
        str(synced_audio_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    temp_video.unlink(missing_ok=True)
    if result.returncode != 0 or not output_path.exists():
        message = result.stderr or result.stdout or "ffmpeg 合并失败"
        raise RuntimeError(message)
    return output_path, synced_audio_path


def probe_audio_duration(audio_path: Path) -> float:
    try:
        with wave.open(str(audio_path), "rb") as wav_file:
            rate = wav_file.getframerate()
            frames = wav_file.getnframes()
            if rate <= 0:
                return 3.0
            return max(1.0, min(120.0, frames / rate))
    except wave.Error:
        return 3.0
