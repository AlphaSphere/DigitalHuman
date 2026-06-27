"""
用途：在 Windows 本地部署 CosyVoice 官方 FastAPI（端口 50000），供 8002 包装服务调用真实 AI 配音。

步骤：
1. clone FunAudioLLM/CosyVoice 到 external/CosyVoice
2. 用 ModelScope 下载 CosyVoice-300M-SFT 模型（约 2GB）
3. 安装 CosyVoice 依赖到独立 venv（避免污染主环境）
4. 启动 runtime/python/fastapi/server.py

用法：
  python scripts/windows/setup_cosyvoice.py install   # 首次安装
  python scripts/windows/setup_cosyvoice.py start     # 启动服务
  python scripts/windows/setup_cosyvoice.py status    # 检查 50000 健康
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from urllib import request
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXTERNAL_DIR = PROJECT_ROOT / "external"
COSYVOICE_DIR = EXTERNAL_DIR / "CosyVoice"
MODEL_DIR = COSYVOICE_DIR / "pretrained_models" / "CosyVoice-300M-SFT"
VENV_DIR = PROJECT_ROOT / "storage" / "venvs" / "cosyvoice"
FASTAPI_DIR = COSYVOICE_DIR / "runtime" / "python" / "fastapi"
COSYVOICE_PORT = 50000
MODELSCOPE_MODEL_ID = "iic/CosyVoice-300M-SFT"


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print(f">>> {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check)


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_git_repo() -> None:
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    if (COSYVOICE_DIR / ".git").exists():
        print(f"CosyVoice 仓库已存在: {COSYVOICE_DIR}")
        run(["git", "submodule", "update", "--init", "--recursive", "--depth", "1"], cwd=COSYVOICE_DIR)
        return
    clone_urls = [
        "https://github.com/FunAudioLLM/CosyVoice.git",
        "https://ghproxy.net/https://github.com/FunAudioLLM/CosyVoice.git",
    ]
    last_error: Exception | None = None
    for url in clone_urls:
        try:
            run(["git", "clone", "--depth", "1", url, str(COSYVOICE_DIR)])
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if COSYVOICE_DIR.exists():
                import shutil

                shutil.rmtree(COSYVOICE_DIR, ignore_errors=True)
    raise RuntimeError("CosyVoice 仓库 clone 失败，请检查网络或手动下载到 external/CosyVoice") from last_error


def ensure_venv() -> None:
    if venv_python().exists():
        print(f"CosyVoice venv 已存在: {VENV_DIR}")
        return
    VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-m", "venv", str(VENV_DIR)])
    pip = [str(venv_python()), "-m", "pip", "install", "-U", "pip", "wheel", "setuptools"]
    run(pip)
    # Windows 下跳过 grpcio/gradio 等编译困难包，仅安装推理所需依赖
    minimal = [
        "conformer==0.3.2",
        "diffusers==0.29.0",
        "hydra-core==1.3.2",
        "HyperPyYAML==1.2.3",
        "inflect==7.3.1",
        "librosa==0.10.2",
        "modelscope>=1.20.0",
        "omegaconf==2.3.0",
        "onnxruntime==1.18.0",
        "protobuf==4.25",
        "pydantic>=2.7",
        "soundfile==0.12.1",
        "transformers==4.51.3",
        "wetext==0.0.4",
        "x-transformers==2.11.24",
        "numpy==1.26.4",
        "networkx",
        "rich",
        "wget",
        "fastapi",
        "uvicorn",
        "httpx",
        "pydantic-settings",
        "python-multipart",
        "openai-whisper",
        "matplotlib",
        "lightning",
        "pyworld",
        "gdown",
        "pyarrow",
        "peft",
        "onnx",
    ]
    run([str(venv_python()), "-m", "pip", "install", *minimal])
    run(
        [
            str(venv_python()),
            "-m",
            "pip",
            "install",
            "torch",
            "torchaudio",
            "--index-url",
            "https://download.pytorch.org/whl/cu124",
        ]
    )


def ensure_model() -> None:
    if MODEL_DIR.exists() and any(MODEL_DIR.iterdir()):
        print(f"模型已存在: {MODEL_DIR}")
        return
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    script = f"""
from modelscope import snapshot_download
snapshot_download('{MODELSCOPE_MODEL_ID}', local_dir=r'{MODEL_DIR.as_posix()}')
print('模型下载完成')
"""
    run([str(venv_python()), "-c", script])


def kill_port(port: int) -> None:
    result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, check=False)
    for line in result.stdout.splitlines():
        if f":{port}" not in line or "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if parts and parts[-1].isdigit():
            subprocess.run(["taskkill", "/F", "/PID", parts[-1]], capture_output=True, check=False)


def start_server() -> None:
    server_py = FASTAPI_DIR / "server.py"
    if not server_py.exists():
        raise FileNotFoundError(f"未找到 FastAPI 入口: {server_py}，请先运行 install")
    if not MODEL_DIR.exists():
        raise FileNotFoundError(f"未找到模型目录: {MODEL_DIR}，请先运行 install")

    log_dir = PROJECT_ROOT / "storage" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "cosyvoice_upstream.log"

    kill_port(COSYVOICE_PORT)
    time.sleep(0.5)

    cmd = [
        str(venv_python()),
        str(server_py),
        "--port",
        str(COSYVOICE_PORT),
        "--model_dir",
        str(MODEL_DIR),
    ]
    print(f"启动 CosyVoice FastAPI :{COSYVOICE_PORT}，日志 -> {log_file}")
    with log_file.open("a", encoding="utf-8") as log:
        subprocess.Popen(
            cmd,
            cwd=FASTAPI_DIR,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )

    deadline = time.time() + 180
    while time.time() < deadline:
        if check_health():
            print(f"CosyVoice 上游已就绪: http://127.0.0.1:{COSYVOICE_PORT}")
            return
        time.sleep(3)
    raise TimeoutError("CosyVoice 启动超时，请查看 storage/logs/cosyvoice_upstream.log")


def check_health() -> bool:
    try:
        with request.urlopen(f"http://127.0.0.1:{COSYVOICE_PORT}/docs", timeout=3) as resp:
            return resp.status == 200
    except URLError:
        return False


def cmd_install() -> None:
    ensure_git_repo()
    ensure_venv()
    ensure_model()
    print("\n安装完成。下一步：")
    print("  1. python scripts/windows/setup_cosyvoice.py start")
    print("  2. 确认 .env 中 COSYVOICE_UPSTREAM_URL=http://127.0.0.1:50000")
    print("  3. 运行 scripts/windows/重启模型服务.bat")


def cmd_status() -> int:
    ok = check_health()
    print(f"CosyVoice :{COSYVOICE_PORT} -> {'就绪' if ok else '未运行'}")
    print(f"模型目录: {MODEL_DIR} ({'存在' if MODEL_DIR.exists() else '缺失'})")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="CosyVoice 本地部署工具")
    parser.add_argument("action", choices=["install", "start", "status"], help="install | start | status")
    args = parser.parse_args()
    if args.action == "install":
        cmd_install()
        return 0
    if args.action == "start":
        start_server()
        return 0
    return cmd_status()


if __name__ == "__main__":
    raise SystemExit(main())
