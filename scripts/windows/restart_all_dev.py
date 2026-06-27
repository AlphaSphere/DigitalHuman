"""
用途：重启 8001 API、8002/8003/8004 模型服务与 5173 前端（Windows）。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib import request
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT / "scripts" / "windows") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "windows"))

from combined_launcher import (  # noqa: E402
    BACKEND_DIR,
    FRONTEND_DIR,
    build_local_env,
    ensure_model_service_deps,
    load_project_dotenv,
    start_model_bridge_services,
    wait_for_url,
)

PORTS = (5173, 8000, 8001, 8002, 8003, 8004)
API_PORT = 8001


def kill_listening_port(port: int) -> None:
    result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, check=False)
    pids: set[str] = set()
    for line in result.stdout.splitlines():
        if f":{port}" not in line or "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if parts:
            pids.add(parts[-1])
    for pid in pids:
        if pid.isdigit() and int(pid) > 0:
            subprocess.run(["taskkill", "/F", "/T", "/PID", pid], capture_output=True, check=False)
            print(f"已结束占用 {port} 的进程 PID={pid}")


def resolve_npm() -> str:
    for candidate in ("npm.cmd", "npm"):
        path = subprocess.run(["where", candidate], capture_output=True, text=True, check=False)
        if path.returncode == 0 and path.stdout.strip():
            return path.stdout.strip().splitlines()[0]
    raise RuntimeError("未找到 npm")


def main() -> int:
    load_project_dotenv()
    log_dir = PROJECT_ROOT / "storage" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    print("清理端口占用…")
    for port in PORTS:
        kill_listening_port(port)
        time.sleep(0.3)

    env = build_local_env()
    ensure_model_service_deps()
    start_model_bridge_services(env)

    api_log = (log_dir / "api.log").open("a", encoding="utf-8")
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(API_PORT)],
        cwd=BACKEND_DIR,
        env=env,
        stdout=api_log,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    npm = resolve_npm()
    web_env = os.environ.copy()
    web_env["VITE_DEV_API_TARGET"] = f"http://127.0.0.1:{API_PORT}"
    web_log = (log_dir / "web.log").open("a", encoding="utf-8")
    subprocess.Popen(
        [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
        cwd=FRONTEND_DIR,
        env=web_env,
        stdout=web_log,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    ok = True
    for url in (
        f"http://127.0.0.1:{API_PORT}/health",
        "http://127.0.0.1:8002/health",
        "http://127.0.0.1:8003/health",
        "http://127.0.0.1:8004/health",
        "http://127.0.0.1:5173/",
    ):
        if not wait_for_url(url, timeout_seconds=60):
            print(f"警告：{url} 未就绪")
            ok = False
        else:
            print(f"OK  {url}")

    runtime_url = f"http://127.0.0.1:{API_PORT}/api/system/runtime-info"
    try:
        with request.urlopen(runtime_url, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        if "cosyvoice_ok" not in body:
            print("警告：API 可能仍是旧版本（runtime-info 缺少模型字段）")
            ok = False
    except URLError as exc:
        print(f"无法读取 runtime-info: {exc}")
        ok = False

    if ok:
        print(f"\n全部服务已就绪。API={API_PORT}，前端=http://127.0.0.1:5173/")
        return 0
    print("\n部分服务未就绪，请查看 storage/logs/")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
