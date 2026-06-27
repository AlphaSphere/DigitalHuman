"""
用途：在 Windows 本地部署 TuiliONNX（Ultralight-Digital-Human ONNX 推理），供 8004 包装服务调用。

步骤：
1. clone anliyuan/Ultralight-Digital-Human 到 external/Ultralight-Digital-Human
2. 创建独立 venv，安装 onnxruntime-gpu / opencv / kaldi-native-fbank 等
3. 下载 wenet encoder.onnx
4. 写入 .env（TUILIONNX_REPO_PATH / TUILIONNX_DEFAULT_DATA_PATH）
5. 可选 prepare：用参考口播视频训练/导出数字人素材

用法：
  python scripts/windows/setup_tuilionnx.py install
  python scripts/windows/setup_tuilionnx.py status
  python scripts/windows/setup_tuilionnx.py prepare --video path/to/20fps.mp4
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib import request
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXTERNAL_DIR = PROJECT_ROOT / "external"
REPO_DIR = EXTERNAL_DIR / "Ultralight-Digital-Human"
VENV_DIR = PROJECT_ROOT / "storage" / "venvs" / "tuilionnx"
COSYVOICE_VENV_DIR = PROJECT_ROOT / "storage" / "venvs" / "cosyvoice"
SERVICE_DIR = PROJECT_ROOT / "Services" / "tuilionnx-service"
DEFAULT_AVATAR_DIR = EXTERNAL_DIR / "tuilionnx_avatars" / "default"
ENV_FILE = PROJECT_ROOT / ".env"

ENCODER_DRIVE_ID = "1e4Z9zS053JEWl6Mj3W9Lbc9GDtzHIg6b"
REPO_URLS = [
    "https://github.com/anliyuan/Ultralight-Digital-Human.git",
    "https://ghproxy.net/https://github.com/anliyuan/Ultralight-Digital-Human.git",
]


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    print(f">>> {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=capture, text=True)


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def cosyvoice_python() -> Path:
    if sys.platform == "win32":
        return COSYVOICE_VENV_DIR / "Scripts" / "python.exe"
    return COSYVOICE_VENV_DIR / "bin" / "python"


def _python_has_torch(python_exe: Path) -> bool:
    if not python_exe.exists():
        return False
    result = subprocess.run(
        [str(python_exe), "-c", "import torch; print(torch.__version__)"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def train_python() -> Path:
    """训练/预处理优先复用 CosyVoice venv 里已装好的 torch，避免重复下载 2.5GB。"""
    cosy = cosyvoice_python()
    if _python_has_torch(cosy):
        print(f"复用 CosyVoice venv 进行训练: {cosy}")
        return cosy
    print(f"使用 TuiliONNX venv 进行训练: {venv_python()}")
    return venv_python()


def ensure_git_repo() -> None:
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    if (REPO_DIR / ".git").exists():
        print(f"Ultralight-Digital-Human 已存在: {REPO_DIR}")
        return
    last_error: Exception | None = None
    for url in REPO_URLS:
        try:
            run(["git", "clone", "--depth", "1", url, str(REPO_DIR)])
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if REPO_DIR.exists():
                shutil.rmtree(REPO_DIR, ignore_errors=True)
    raise RuntimeError("Ultralight-Digital-Human clone 失败，请检查网络") from last_error


def ensure_venv() -> None:
    if venv_python().exists():
        print(f"TuiliONNX venv 已存在: {VENV_DIR}")
    else:
        VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
        run([str(venv_python()), "-m", "pip", "install", "-U", "pip", "wheel", "setuptools"])

    deps = [
        "onnxruntime-gpu>=1.18.0",
        "opencv-python>=4.8.0",
        "numpy>=1.26.0",
        "soundfile>=0.12.1",
        "librosa>=0.10.2",
        "kaldi-native-fbank>=1.20.0",
        "scipy>=1.11.0",
        "gdown>=5.2.0",
        "fastapi>=0.115.0",
        "httpx>=0.28.0",
        "pydantic>=2.10.0",
        "pydantic-settings>=2.7.0",
        "uvicorn[standard]>=0.34.0",
    ]
    run([str(venv_python()), "-m", "pip", "install", *deps])
    run([str(venv_python()), "-m", "pip", "install", "-e", str(SERVICE_DIR)])


def ensure_encoder_onnx() -> Path:
    data_utils_dir = REPO_DIR / "data_utils"
    data_utils_dir.mkdir(parents=True, exist_ok=True)
    encoder_path = data_utils_dir / "encoder.onnx"
    if encoder_path.exists() and encoder_path.stat().st_size > 1024:
        print(f"encoder.onnx 已存在: {encoder_path}")
        return encoder_path

    print("正在下载 wenet encoder.onnx …")
    url = f"https://drive.google.com/uc?id={ENCODER_DRIVE_ID}"
    script = f"""
import gdown
gdown.download(r"{url}", r"{encoder_path.as_posix()}", quiet=False)
print("encoder.onnx 下载完成")
"""
    run([str(venv_python()), "-c", script])
    if not encoder_path.exists():
        raise FileNotFoundError(f"encoder.onnx 下载失败: {encoder_path}")
    return encoder_path


def _avatar_ready(data_dir: Path) -> bool:
    return all(
        (data_dir / name).exists()
        for name in ("img_inference", "lms_inference", "unet.onnx", "encoder.onnx")
    )


def _sync_encoder_to_avatar(encoder_path: Path) -> None:
    DEFAULT_AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    target = DEFAULT_AVATAR_DIR / "encoder.onnx"
    if not target.exists():
        shutil.copy2(encoder_path, target)
        print(f"已复制 encoder.onnx -> {target}")


def update_env_file() -> None:
    repo_path = str(REPO_DIR).replace("\\", "/")
    avatar_path = str(DEFAULT_AVATAR_DIR).replace("\\", "/")
    profile_map = json.dumps({"default": avatar_path}, ensure_ascii=False)
    new_vars = {
        "TUILIONNX_REPO_PATH": repo_path,
        "TUILIONNX_DEFAULT_DATA_PATH": avatar_path,
        "TUILIONNX_AVATAR_PROFILE_MAP": profile_map,
        "TUILIONNX_EXECUTION_PROVIDER": "auto",
    }

    existing_lines: list[str] = []
    if ENV_FILE.exists():
        existing_lines = ENV_FILE.read_text(encoding="utf-8").splitlines()

    updated_lines: list[str] = []
    written_keys: set[str] = set()
    for line in existing_lines:
        stripped = line.strip()
        for key, value in new_vars.items():
            if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                line = f"{key}={value}"
                written_keys.add(key)
                break
        updated_lines.append(line)

    missing = {k: v for k, v in new_vars.items() if k not in written_keys}
    if missing:
        updated_lines.append("")
        updated_lines.append("# TuiliONNX / Ultralight-Digital-Human 配置（由 setup_tuilionnx.py 写入）")
        for key, value in missing.items():
            updated_lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    print(f".env 已更新：{', '.join(new_vars.keys())}")


def _ensure_20fps_video(source: Path, target: Path) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("未找到 ffmpeg，请先安装并加入 PATH")
    target.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-vf",
            "fps=20",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(target),
        ]
    )
    return target


def _build_streaming_assets(dataset_dir: Path) -> None:
    """从训练数据目录生成流式推理所需的 img_inference / lms_inference。"""
    full_body = dataset_dir / "full_body_img"
    landmarks = dataset_dir / "landmarks"
    img_out = dataset_dir / "img_inference"
    lms_out = dataset_dir / "lms_inference"
    img_out.mkdir(exist_ok=True)
    lms_out.mkdir(exist_ok=True)

    images = sorted(full_body.glob("*.jpg"), key=lambda p: int(p.stem))
    landmark_files = sorted(landmarks.glob("*.lms"), key=lambda p: int(p.stem))
    if not images or not landmark_files:
        raise RuntimeError("预处理结果缺少 full_body_img 或 landmarks")

    # 取前 20 秒静音段（20fps * 20s = 400 帧），不足则全量复制
    limit = min(len(images), len(landmark_files), 400)
    for index in range(limit):
        shutil.copy2(images[index], img_out / f"{index}.jpg")
        shutil.copy2(landmark_files[index], lms_out / f"{index}.lms")


def cmd_prepare(video_path: Path, epochs: int = 50) -> None:
    if not venv_python().exists() or not REPO_DIR.exists():
        raise RuntimeError("请先运行 install")

    video_path = video_path.resolve()
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    work_dir = EXTERNAL_DIR / "tuilionnx_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    fps20_video = work_dir / "reference_20fps.mp4"
    _ensure_20fps_video(video_path, fps20_video)

    # 预处理/训练依赖 torch：优先复用 CosyVoice venv
    train_py = train_python()
    if train_py == venv_python():
        if not train_py.exists():
            raise RuntimeError("请先运行 install")
        if not _python_has_torch(train_py):
            run(
                [
                    str(train_py),
                    "-m",
                    "pip",
                    "install",
                    "torch",
                    "torchaudio",
                    "torchvision",
                    "--index-url",
                    "https://download.pytorch.org/whl/cu124",
                ]
            )
    # 训练依赖从 PyPI 装；torch/torchvision/torchaudio 必须走 cu124 索引，避免被 PyPI 覆盖成 CPU 版 torch
    run(
        [
            str(train_py),
            "-m",
            "pip",
            "install",
            "opencv-python>=4.8.0",
            "transformers>=4.51.0",
            "omegaconf==2.3.0",
            "HyperPyYAML==1.2.3",
            "matplotlib",
            "tqdm",
        ]
    )
    if train_py == cosyvoice_python():
        run(
            [
                str(train_py),
                "-m",
                "pip",
                "install",
                "torch==2.6.0+cu124",
                "torchvision==0.21.0+cu124",
                "torchaudio==2.6.0+cu124",
                "--index-url",
                "https://download.pytorch.org/whl/cu124",
            ]
        )

    encoder_path = ensure_encoder_onnx()
    process_py = REPO_DIR / "data_utils" / "process.py"
    run([str(train_py), str(process_py), str(fps20_video), "--asr", "wenet"], cwd=REPO_DIR / "data_utils")

    dataset_dir = fps20_video.parent
    checkpoint_dir = work_dir / "checkpoint"
    run(
        [
            str(train_py),
            str(REPO_DIR / "train.py"),
            "--dataset_dir",
            str(dataset_dir),
            "--save_dir",
            str(checkpoint_dir),
            "--asr",
            "wenet",
            "--epochs",
            str(epochs),
        ],
        cwd=REPO_DIR,
    )

    # 导出 unet.onnx
    export_script = f"""
import sys
from pathlib import Path
import torch
sys.path.insert(0, r'{REPO_DIR.as_posix()}')
from unet import Model

ckpt_dir = Path(r'{checkpoint_dir.as_posix()}')
ckpts = sorted(ckpt_dir.glob('*.pth'), key=lambda p: p.stat().st_mtime)
if not ckpts:
    raise SystemExit('未找到训练 checkpoint')
ckpt = ckpts[-1]
print('使用 checkpoint:', ckpt)

net = Model(6).eval()
net.load_state_dict(torch.load(ckpt, map_location='cpu'))
img = torch.zeros([1, 6, 160, 160])
audio = torch.zeros([1, 128, 16, 32])
out_path = Path(r'{DEFAULT_AVATAR_DIR.as_posix()}') / 'unet.onnx'
out_path.parent.mkdir(parents=True, exist_ok=True)
torch.onnx.export(
    net,
    (img, audio),
    str(out_path),
    input_names=['input', 'audio'],
    output_names=['output'],
    opset_version=11,
    export_params=True,
)
print('unet.onnx 导出完成:', out_path)
"""
    run([str(train_py), "-c", export_script])

    DEFAULT_AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(encoder_path, DEFAULT_AVATAR_DIR / "encoder.onnx")
    _build_streaming_assets(dataset_dir)

    # 复制 img/lms 到 default avatar
    for folder in ("img_inference", "lms_inference"):
        src = dataset_dir / folder
        dst = DEFAULT_AVATAR_DIR / folder
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    update_env_file()
    print(f"\n数字人素材已就绪: {DEFAULT_AVATAR_DIR}")
    print("请运行 scripts/windows/重启模型服务.bat 使 8004 切换为 local-onnx 模式。")


def cmd_install() -> None:
    ensure_git_repo()
    ensure_venv()
    encoder_path = ensure_encoder_onnx()
    _sync_encoder_to_avatar(encoder_path)
    update_env_file()

    ready = _avatar_ready(DEFAULT_AVATAR_DIR)
    print("\n========================================")
    print("  TuiliONNX / ONNX 运行时安装完成")
    print("========================================")
    print(f"  仓库: {REPO_DIR}")
    print(f"  venv: {VENV_DIR}")
    print(f"  encoder.onnx: {encoder_path}")
    if ready:
        print(f"  默认数字人素材: {DEFAULT_AVATAR_DIR} （已就绪）")
    else:
        print("  默认数字人素材: 尚未就绪（缺少 unet.onnx / img_inference / lms_inference）")
        print("  下一步二选一：")
        print("    1. python scripts/windows/setup_tuilionnx.py prepare --video 你的20fps口播.mp4")
        print("    2. 手动把训练好的素材放到 external/tuilionnx_avatars/default/")
    print("\n然后运行 scripts/windows/重启模型服务.bat")


def cmd_status() -> int:
    ok_repo = (REPO_DIR / "dihuman_run.py").exists()
    ok_venv = venv_python().exists()
    ok_encoder = (REPO_DIR / "data_utils" / "encoder.onnx").exists()
    ok_avatar = _avatar_ready(DEFAULT_AVATAR_DIR)

    print(f"Ultralight 仓库: {'OK' if ok_repo else '缺失'} ({REPO_DIR})")
    print(f"TuiliONNX venv: {'OK' if ok_venv else '缺失'} ({VENV_DIR})")
    print(f"encoder.onnx: {'OK' if ok_encoder else '缺失'}")
    print(f"默认数字人素材: {'OK' if ok_avatar else '缺失'} ({DEFAULT_AVATAR_DIR})")

    if ok_avatar:
        try:
            with request.urlopen("http://127.0.0.1:8004/health", timeout=3) as resp:
                print(f"8004 健康检查: {resp.read().decode()[:200]}")
        except URLError:
            print("8004 服务未运行，请运行 重启模型服务.bat")

    return 0 if ok_repo and ok_venv and ok_encoder else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="TuiliONNX / Ultralight-Digital-Human 部署工具")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("install", help="安装 ONNX 运行时与 Ultralight 仓库")
    sub.add_parser("status", help="检查安装状态")

    prepare = sub.add_parser("prepare", help="用参考视频训练并导出默认数字人素材")
    prepare.add_argument("--video", required=True, help="参考口播视频（会自动转为 20fps）")
    prepare.add_argument("--epochs", type=int, default=50, help="训练轮数，默认 50")

    args = parser.parse_args()
    if args.action == "install":
        cmd_install()
        return 0
    if args.action == "prepare":
        cmd_prepare(Path(args.video), epochs=args.epochs)
        return 0
    return cmd_status()


if __name__ == "__main__":
    raise SystemExit(main())
