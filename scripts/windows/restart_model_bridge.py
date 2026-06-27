"""
用途：在不重启整个桌面客户端的情况下，重启 8002/8003/8004 模型包装服务（方案 A 占位模式）。
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

from combined_launcher import (  # noqa: E402
    build_local_env,
    ensure_model_service_deps,
    load_project_dotenv,
    pick_env,
    start_model_bridge_services,
    wait_for_url,
)


def kill_listening_port(port: int) -> None:
    """Windows：结束占用指定端口的监听进程。"""
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
    load_project_dotenv()
    stub = pick_env("ALLOW_MODEL_SERVICE_STUB_OUTPUT", "").lower() in ("1", "true", "yes")
    print("=" * 48)
    print("  重启模型包装服务（CosyVoice / HeyGem / TuiliONNX）")
    print(f"  ALLOW_MODEL_SERVICE_STUB_OUTPUT={stub}")
    print("=" * 48)

    for port in (8002, 8003, 8004):
        kill_listening_port(port)
        time.sleep(0.4)

    ensure_model_service_deps()
    local_env = build_local_env()
    start_model_bridge_services(local_env)

    ok = True
    for port in (8002, 8003, 8004):
        url = f"http://127.0.0.1:{port}/health"
        if not wait_for_url(url, timeout_seconds=30):
            print(f"警告：{url} 未在 30 秒内就绪")
            ok = False
            continue
        try:
            with request.urlopen(url, timeout=3) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            print(f"OK  {url} -> {body.strip()}")
        except URLError as exc:
            print(f"警告：无法读取 {url}: {exc}")
            ok = False

    if ok:
        cosy = pick_env("COSYVOICE_UPSTREAM_URL") or pick_env("COSYVOICE_MODEL_DIR")
        if cosy and not stub:
            print("\n模型服务已就绪（CosyVoice 真实 AI 配音）。请在进度页点击「重新生成」。")
        elif stub:
            print("\n模型服务已以占位模式就绪。请在进度页点击「重新生成」。")
        else:
            print("\n模型服务已重启。请在进度页点击「重新生成」。")
        return 0
    print("\n部分服务未就绪，请查看 storage/logs/ 下 cosyvoice.log / heygem.log / tuilionnx.log")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
