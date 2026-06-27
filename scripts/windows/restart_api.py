"""
用途：重启后端 API（8000），使 runtime-info 等最新接口生效。
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from urllib import request
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT / "scripts" / "windows") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "windows"))

from combined_launcher import BACKEND_DIR, build_local_env, wait_for_url  # noqa: E402


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
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, check=False)
            print(f"已结束占用 {port} 端口的进程 PID={pid}")


def main() -> int:
    kill_listening_port(8000)
    time.sleep(2)

    env = build_local_env()
    log_dir = PROJECT_ROOT / "storage" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = (log_dir / "api.log").open("a", encoding="utf-8")
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    health_url = "http://127.0.0.1:8000/health"
    runtime_url = "http://127.0.0.1:8000/api/system/runtime-info"
    if not wait_for_url(health_url, timeout_seconds=45):
        print(f"API 未在 45 秒内就绪，请查看 storage/logs/api.log")
        return 1

    try:
        with request.urlopen(runtime_url, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        print(f"OK  {runtime_url}")
        if "cosyvoice_ok" in body:
            print("runtime-info 已包含模型服务探测字段。")
        else:
            print("警告：runtime-info 仍缺少模型服务字段，请确认 Backend 代码已更新。")
            return 1
    except URLError as exc:
        print(f"无法读取 runtime-info: {exc}")
        return 1

    print("后端 API 已重启。请刷新配置页查看模型服务状态。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
