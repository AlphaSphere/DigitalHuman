"""
用途：在 Windows 本地部署 Duix.Avatar Docker 服务（端口 8383），供 8003 包装服务调用真实 HeyGem 数字人。

步骤：
1. 检测 Docker Desktop 是否安装并运行
2. 拉取 duixcom/duix-avatar 镜像（全版约 70GB，需提前预留磁盘空间）
3. 启动容器，将 storage 目录挂载到容器内，实现路径共享
4. 在 .env 写入必要配置变量

用法：
  python scripts/windows/setup_heygem.py check    # 检查 Docker 状态
  python scripts/windows/setup_heygem.py pull     # 拉取镜像（需网络，约 70GB）
  python scripts/windows/setup_heygem.py start    # 启动容器
  python scripts/windows/setup_heygem.py stop     # 停止容器
  python scripts/windows/setup_heygem.py status   # 检查 :8383 健康状态
  python scripts/windows/setup_heygem.py install  # 完整安装（pull + start + 写 .env）
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib import request
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_DIR = PROJECT_ROOT / "storage"
ENV_FILE = PROJECT_ROOT / ".env"

DOCKER_IMAGE = "guiji2025/duix.avatar:latest"
CONTAINER_NAME = "duix-avatar-gen-video"
HOST_PORT = 8383
CONTAINER_PORT = 8383

# 宿主机 storage 目录 → 容器内挂载路径
HOST_STORAGE_ROOT = STORAGE_DIR
CONTAINER_STORAGE_ROOT = "/code/data"

# 官方 docker-compose 指定启动命令（镜像本身无默认 CMD/ENTRYPOINT）
CONTAINER_COMMAND = ["python", "/code/app_local.py"]

# Duix.Avatar 数据目录（数字人模型、素材）
DUIX_DATA_DIR = PROJECT_ROOT / "external" / "duix_avatar_data"


def run(cmd: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    print(f">>> {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def check_docker() -> bool:
    """检测 Docker Desktop 是否已安装并运行。"""
    try:
        result = subprocess.run(
            ["docker", "info"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        print("Docker 运行正常。")
        return True
    except FileNotFoundError:
        print(
            "\n[错误] 未找到 docker 命令。\n"
            "请先安装 Docker Desktop for Windows：\n"
            "  https://www.docker.com/products/docker-desktop/\n"
            "安装完成后重启本脚本。"
        )
        return False
    except subprocess.CalledProcessError:
        print(
            "\n[错误] Docker 已安装但未运行。\n"
            "请打开 Docker Desktop 并等待其完全启动（系统托盘出现鲸鱼图标）后重试。"
        )
        return False
    except subprocess.TimeoutExpired:
        print("[错误] Docker 响应超时，请检查 Docker Desktop 是否正在启动中。")
        return False


def image_exists() -> bool:
    """检查本地是否已有 Duix.Avatar 镜像。"""
    result = subprocess.run(
        ["docker", "images", "-q", DOCKER_IMAGE],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def pull_image() -> None:
    """拉取 Duix.Avatar 完整版镜像。

    注意：完整版约 70GB，拉取时间较长，请确保网络稳定且磁盘有足够空间。
    """
    if image_exists():
        print(f"镜像已存在: {DOCKER_IMAGE}，跳过拉取。")
        return
    print(f"\n开始拉取 {DOCKER_IMAGE}（完整版约 70GB，请耐心等待）…")
    run(["docker", "pull", DOCKER_IMAGE])
    print("镜像拉取完成。")


def container_running() -> bool:
    """检查容器是否正在运行。"""
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={CONTAINER_NAME}"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def container_exists() -> bool:
    """检查容器是否存在（包含已停止的）。"""
    result = subprocess.run(
        ["docker", "ps", "-aq", "-f", f"name={CONTAINER_NAME}"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def start_container() -> None:
    """启动 Duix.Avatar 容器，挂载 storage 目录实现路径共享。"""
    if container_running():
        print(f"容器 {CONTAINER_NAME} 已在运行。")
        return

    if container_exists():
        print(f"容器 {CONTAINER_NAME} 已存在但未运行，正在启动…")
        run(["docker", "start", CONTAINER_NAME])
        _wait_for_health()
        return

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    DUIX_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Windows 路径需转为正斜杠格式供 Docker 使用
    host_storage = str(HOST_STORAGE_ROOT).replace("\\", "/")
    host_data = str(DUIX_DATA_DIR).replace("\\", "/")

    cmd = [
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "--restart", "unless-stopped",
        # 端口映射
        "-p", f"{HOST_PORT}:{CONTAINER_PORT}",
        # storage 目录挂载（宿主机音频/视频文件共享给容器）
        "-v", f"{host_storage}:{CONTAINER_STORAGE_ROOT}",
        # 数字人素材目录
        "-v", f"{host_data}:/duix_avatar_data",
        # Duix.Avatar 视频服务需要较大的共享内存与 GPU 访问
        "--shm-size", "8g",
        "--privileged",
        # 官方 compose 中的 CUDA 内存配置
        "-e", "PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512",
        # GPU 支持（Docker Desktop + WSL2 + NVIDIA 驱动）
        "--gpus", "all",
        DOCKER_IMAGE,
        *CONTAINER_COMMAND,
    ]

    print(f"\n正在启动容器 {CONTAINER_NAME}…")
    try:
        run(cmd)
    except subprocess.CalledProcessError:
        # GPU 不可用时降级为 CPU 模式
        print("[警告] GPU 启动失败，尝试 CPU 模式（速度较慢）…")
        cmd_no_gpu = [c for c in cmd if c not in ("--gpus", "all")]
        run(cmd_no_gpu)

    _wait_for_health()


def _duix_health_url() -> str:
    """Duix.Avatar 无 /health 端点，用 /easy/query 探测服务是否在线。"""
    return f"http://127.0.0.1:{HOST_PORT}/easy/query?code=healthcheck"


def _wait_for_health(timeout_seconds: int = 120) -> None:
    """等待 :8383 API 可访问。"""
    url = _duix_health_url()
    deadline = time.monotonic() + timeout_seconds
    print(f"等待 Duix.Avatar :8383 就绪（最长 {timeout_seconds}s）…")
    while time.monotonic() < deadline:
        try:
            with request.urlopen(url, timeout=3) as resp:
                if resp.status < 500:
                    print("Duix.Avatar :8383 已就绪！")
                    return
        except URLError as exc:
            # HTTP 4xx 说明服务已启动（如任务不存在），仅连接失败才继续等待
            if hasattr(exc, "code") and exc.code and exc.code < 500:
                print("Duix.Avatar :8383 已就绪！")
                return
        except OSError:
            pass
        time.sleep(3)
    print(f"[警告] 等待超时，:8383 仍不可访问。容器可能还在初始化，稍后可运行 status 再检查。")


def stop_container() -> None:
    """停止 Duix.Avatar 容器。"""
    if not container_running():
        print(f"容器 {CONTAINER_NAME} 未在运行。")
        return
    run(["docker", "stop", CONTAINER_NAME])
    print(f"容器 {CONTAINER_NAME} 已停止。")


def check_status() -> bool:
    """检查 :8383 API 可达性。"""
    url = _duix_health_url()
    try:
        with request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode()
            print(f"Duix.Avatar :8383 健康检查通过: {body[:200]}")
            return True
    except URLError as exc:
        if hasattr(exc, "code") and exc.code and exc.code < 500:
            print(f"Duix.Avatar :8383 健康检查通过（HTTP {exc.code}）")
            return True
        print(f"Duix.Avatar :8383 不可访问: {exc}")
        return False
    except OSError as exc:
        print(f"Duix.Avatar :8383 不可访问: {exc}")
        return False


def update_env_file() -> None:
    """将 HeyGem 相关配置写入 .env 文件（已存在的行不重复写）。"""
    host_storage = str(HOST_STORAGE_ROOT).replace("\\", "/")
    new_vars: dict[str, str] = {
        "HEYGEM_VIDEO_BASE_URL": f"http://127.0.0.1:{HOST_PORT}",
        "HEYGEM_HOST_STORAGE_ROOT": host_storage,
        "HEYGEM_CONTAINER_STORAGE_ROOT": CONTAINER_STORAGE_ROOT,
    }

    existing_lines: list[str] = []
    if ENV_FILE.exists():
        existing_lines = ENV_FILE.read_text(encoding="utf-8").splitlines()

    # 更新已存在的行，收集缺失的 key
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

    # 追加缺失的 key
    missing = {k: v for k, v in new_vars.items() if k not in written_keys}
    if missing:
        updated_lines.append("")
        updated_lines.append("# HeyGem / Duix.Avatar 配置（由 setup_heygem.py 写入）")
        for key, value in missing.items():
            updated_lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    print(f".env 已更新：{', '.join(new_vars.keys())}")


def cmd_install() -> None:
    """完整安装：检查 Docker → 拉取镜像 → 启动容器 → 写 .env。"""
    if not check_docker():
        sys.exit(1)
    pull_image()
    start_container()
    update_env_file()
    print(
        "\n========================================\n"
        "  HeyGem / Duix.Avatar 安装完成！\n"
        "========================================\n"
        "接下来：\n"
        "  1. 运行 scripts/windows/重启模型服务.bat\n"
        "  2. 配置页确认 HeyGem 8003 模式为 official-video-api\n"
        "  3. 在配置页选择「预设数字人」并确保 HEYGEM_DEFAULT_VIDEO_PATH 或\n"
        "     HEYGEM_AVATAR_PROFILE_MAP 指向参考视频文件\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Duix.Avatar / HeyGem Docker 部署工具")
    parser.add_argument(
        "command",
        choices=["check", "pull", "start", "stop", "status", "install"],
        help="操作命令",
    )
    args = parser.parse_args()

    match args.command:
        case "check":
            sys.exit(0 if check_docker() else 1)
        case "pull":
            if not check_docker():
                sys.exit(1)
            pull_image()
        case "start":
            if not check_docker():
                sys.exit(1)
            start_container()
        case "stop":
            stop_container()
        case "status":
            sys.exit(0 if check_status() else 1)
        case "install":
            cmd_install()


if __name__ == "__main__":
    main()
