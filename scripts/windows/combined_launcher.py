"""

DigitalHuman 桌面客户端启动器（对齐 KrLongAI combined_launcher 模式）。



本地直接运行，不依赖 Docker：

- FastAPI (uvicorn) + Vite 前端 + SQLite

- Celery 同步模式（无需 Redis / 独立 Worker）

- pywebview 原生窗口，样式与 Web 版一致

- Chrome 后台 9222 仅用于 Playwright 发布

"""



from __future__ import annotations



import atexit

import logging

import os

import shutil

import subprocess

import sys

import threading

import time

from pathlib import Path

from urllib import request

from urllib.error import URLError



logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)



PROJECT_ROOT = Path(__file__).resolve().parents[2]

BACKEND_DIR = PROJECT_ROOT / "Backend"

FRONTEND_DIR = PROJECT_ROOT / "Frontend"

COSYVOICE_SERVICE_DIR = PROJECT_ROOT / "Services" / "cosyvoice-service"

HEYGEM_SERVICE_DIR = PROJECT_ROOT / "Services" / "heygem-service"

TUILIONNX_SERVICE_DIR = PROJECT_ROOT / "Services" / "tuilionnx-service"

STORAGE_DIR = PROJECT_ROOT / "storage"

COSYVOICE_VENV_PYTHON = STORAGE_DIR / "venvs" / "cosyvoice" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
TUILIONNX_VENV_PYTHON = STORAGE_DIR / "venvs" / "tuilionnx" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

LOG_DIR = STORAGE_DIR / "logs"



WEB_URL = os.environ.get("DESKTOP_WEB_URL", "http://127.0.0.1:5173/tasks/new")

API_HEALTH_URL = os.environ.get("DESKTOP_API_HEALTH_URL", "http://127.0.0.1:8000/health")

WINDOW_TITLE = os.environ.get("DESKTOP_WINDOW_TITLE", "Digital Human Studio · 数字人追爆")

WINDOW_WIDTH = int(os.environ.get("DESKTOP_WINDOW_WIDTH", "1440"))

WINDOW_HEIGHT = int(os.environ.get("DESKTOP_WINDOW_HEIGHT", "920"))



_local_processes: list[subprocess.Popen] = []





def refresh_path() -> None:
    """合并系统与用户 PATH，确保刚安装的 Node 等可被找到。"""
    if os.name != "nt":
        return
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
        ) as key:
            machine = winreg.QueryValueEx(key, "Path")[0]
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            user = winreg.QueryValueEx(key, "Path")[0]
        os.environ["Path"] = f"{machine};{user}"
    except OSError:
        pass


def shutil_which(name: str) -> str | None:
    refresh_path()
    return resolve_executable(name)


def resolve_executable(name: str) -> str | None:
    """解析可执行文件路径（Windows 下 npm 等需 .cmd）。"""
    path = shutil.which(name)
    if path:
        return path
    if os.name == "nt":
        return shutil.which(f"{name}.cmd") or shutil.which(f"{name}.exe")
    return None


def load_project_dotenv() -> dict[str, str]:
    """读取项目根 .env，供启动器继承用户配置（Stub、Whisper 等）。"""
    target = PROJECT_ROOT / ".env"
    merged: dict[str, str] = {}
    if not target.exists():
        return merged
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        merged[key.strip()] = value.strip()
    return merged


def pick_env(key: str, default: str = "") -> str:
    """优先系统环境变量，其次 .env 文件，最后默认值。"""
    if os.environ.get(key) not in (None, ""):
        return os.environ[key]
    dotenv = load_project_dotenv()
    if dotenv.get(key) not in (None, ""):
        return dotenv[key]
    return default





def build_local_env() -> dict[str, str]:

    """组装本地桌面模式环境变量（绝对路径，避免 cwd 差异）。"""

    env = os.environ.copy()

    db_path = (STORAGE_DIR / "digital_human.db").resolve()



    env.update(

        {

            "LOCAL_DESKTOP_MODE": "true",

            "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",

            "REDIS_URL": "redis://127.0.0.1:6379/0",

            "STORAGE_ROOT": str(STORAGE_DIR.resolve()),

            "MUSIC_LIBRARY_PATH": str((STORAGE_DIR / "music").resolve()),

            "WHISPER_BASE_URL": pick_env("WHISPER_BASE_URL", ""),

            "COZYVOICE_BASE_URL": pick_env("COZYVOICE_BASE_URL", "http://127.0.0.1:8002"),

            "HEYGEM_BASE_URL": pick_env("HEYGEM_BASE_URL", "http://127.0.0.1:8003"),

            "TUILIONNX_BASE_URL": pick_env("TUILIONNX_BASE_URL", "http://127.0.0.1:8004"),

            "PLAYWRIGHT_CHROME_CDP_URL": pick_env("PLAYWRIGHT_CHROME_CDP_URL", "http://127.0.0.1:9222"),

            "USE_STUB_MODEL_ADAPTERS": pick_env("USE_STUB_MODEL_ADAPTERS", "false"),

            "DEEPSEEK_API_KEY": pick_env("DEEPSEEK_API_KEY", ""),

            "DEEPSEEK_BASE_URL": pick_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),

            "DEEPSEEK_MODEL": pick_env("DEEPSEEK_MODEL", "deepseek-chat"),

            "ENABLE_LLM_REWRITE": pick_env("ENABLE_LLM_REWRITE", "true"),

            "VITE_API_BASE_URL": "/api",

            "VITE_DEV_API_TARGET": pick_env("VITE_DEV_API_TARGET", "http://127.0.0.1:8000"),

            "PYTHONIOENCODING": "utf-8",

        }

    )

    return env





def sync_dotenv(local_env: dict[str, str]) -> None:

    """将本地关键配置写入项目根 .env，便于手动调试时一致。"""

    template = PROJECT_ROOT / ".env.local.example"

    target = PROJECT_ROOT / ".env"

    if not target.exists() and template.exists():

        shutil.copy(template, target)



    lines: list[str] = []

    if target.exists():

        lines = target.read_text(encoding="utf-8").splitlines()



    overrides = {

        "LOCAL_DESKTOP_MODE": "true",

        "DATABASE_URL": local_env["DATABASE_URL"],

        "STORAGE_ROOT": local_env["STORAGE_ROOT"],

        "MUSIC_LIBRARY_PATH": local_env["MUSIC_LIBRARY_PATH"],

        "PLAYWRIGHT_CHROME_CDP_URL": local_env["PLAYWRIGHT_CHROME_CDP_URL"],

        "COZYVOICE_BASE_URL": local_env["COZYVOICE_BASE_URL"],

        "HEYGEM_BASE_URL": local_env["HEYGEM_BASE_URL"],

        "TUILIONNX_BASE_URL": local_env["TUILIONNX_BASE_URL"],

        "VITE_API_BASE_URL": local_env["VITE_API_BASE_URL"],

        "USE_STUB_MODEL_ADAPTERS": local_env["USE_STUB_MODEL_ADAPTERS"],

    }

    # 仅当 .env 或启动参数里显式配置了 Whisper 地址时才写入，避免覆盖为空（走本地 CLI）
    if local_env.get("WHISPER_BASE_URL"):
        overrides["WHISPER_BASE_URL"] = local_env["WHISPER_BASE_URL"]



    merged: dict[str, str] = {}

    for line in lines:

        if not line.strip() or line.strip().startswith("#") or "=" not in line:

            continue

        key, value = line.split("=", 1)

        merged[key.strip()] = value.strip()

    merged.update(overrides)



    content = "\n".join(f"{key}={value}" for key, value in merged.items()) + "\n"

    target.write_text(content, encoding="utf-8")





def ensure_desktop_deps() -> None:

    """安装桌面窗口依赖。"""

    try:

        import webview  # noqa: F401

    except ImportError:

        logger.info("正在安装 pywebview...")

        subprocess.check_call(

            [sys.executable, "-m", "pip", "install", "-r", str(Path(__file__).with_name("requirements-desktop.txt"))]

        )





def ensure_backend_deps() -> None:

    """安装后端 Python 依赖。"""

    logger.info("检查后端依赖...")

    subprocess.check_call(

        [sys.executable, "-m", "pip", "install", "-e", str(BACKEND_DIR)],

        cwd=BACKEND_DIR,

    )





def ensure_frontend_deps() -> None:

    """安装前端 Node 依赖。"""

    npm = resolve_executable("npm")
    if npm is None:
        raise RuntimeError("未找到 npm，请先安装 Node.js 18+ 并加入 PATH。")
    if (FRONTEND_DIR / "node_modules").exists():
        return
    logger.info("首次运行，正在 npm install...")
    subprocess.check_call([npm, "install"], cwd=FRONTEND_DIR)





def run_migrations(local_env: dict[str, str]) -> None:

    """执行 Alembic 迁移（失败时不阻断，lifespan 仍会 create_all）。"""

    logger.info("执行数据库迁移...")

    result = subprocess.run(

        [sys.executable, "-m", "alembic", "upgrade", "head"],

        cwd=BACKEND_DIR,

        env=local_env,

        capture_output=True,

        text=True,

    )

    if result.returncode != 0:

        logger.warning("Alembic 迁移未完全成功，将依赖启动时自动建表: %s", (result.stderr or result.stdout).strip())





def start_local_process(name: str, cmd: list[str], cwd: Path, local_env: dict[str, str]) -> subprocess.Popen:

    """启动本地子进程并写入日志文件。"""

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_path = LOG_DIR / f"{name}.log"

    log_file = log_path.open("a", encoding="utf-8")

    logger.info("启动 %s: %s", name, " ".join(cmd))

    process = subprocess.Popen(

        cmd,

        cwd=cwd,

        env=local_env,

        stdout=log_file,

        stderr=subprocess.STDOUT,

        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),

    )

    _local_processes.append(process)

    return process





def ensure_model_service_deps() -> None:

    """安装 CosyVoice / HeyGem 包装微服务依赖。"""

    for service_dir in (COSYVOICE_SERVICE_DIR, HEYGEM_SERVICE_DIR, TUILIONNX_SERVICE_DIR):

        if not service_dir.exists():

            logger.warning("模型包装服务目录不存在: %s", service_dir)

            continue

        logger.info("检查模型包装服务依赖: %s", service_dir.name)

        subprocess.check_call(

            [sys.executable, "-m", "pip", "install", "-e", str(service_dir)],

            cwd=service_dir,

        )





def _model_bridge_ready(prefix: str, keys: tuple[str, ...]) -> bool:

    return any(pick_env(key) for key in keys)


def _ensure_cosyvoice_upstream_running() -> None:
    """若 .env 配置了本地 CosyVoice 上游，则确保 :50000 FastAPI 已启动。"""
    upstream = pick_env("COSYVOICE_UPSTREAM_URL", "")
    if not upstream or "127.0.0.1:50000" not in upstream:
        return
    if wait_for_url("http://127.0.0.1:50000/docs", timeout_seconds=3):
        logger.info("CosyVoice 上游 :50000 已在运行。")
        return
    model_dir = PROJECT_ROOT / "external" / "CosyVoice" / "pretrained_models" / "CosyVoice-300M-SFT"
    setup_script = PROJECT_ROOT / "scripts" / "windows" / "setup_cosyvoice.py"
    if not model_dir.exists() or not setup_script.exists():
        logger.warning(
            "已配置 COSYVOICE_UPSTREAM_URL=:50000，但模型未安装。请运行: python scripts/windows/setup_cosyvoice.py install"
        )
        return
    logger.info("正在启动 CosyVoice 上游服务 :50000 …")
    subprocess.run([sys.executable, str(setup_script), "start"], check=False, cwd=PROJECT_ROOT)


def _ensure_heygem_upstream_running() -> None:
    """若 .env 配置了 HEYGEM_VIDEO_BASE_URL，检测 Duix.Avatar :8383 是否可达。

    不可达时打印安装提示，不阻塞启动流程（8003 会自动降级为 stub）。
    """
    heygem_url = pick_env("HEYGEM_VIDEO_BASE_URL", "")
    if not heygem_url:
        return
    if wait_for_url(f"{heygem_url.rstrip('/')}/easy/query?code=healthcheck", timeout_seconds=5):
        logger.info("HeyGem/Duix.Avatar 上游已在运行: %s", heygem_url)
        return
    setup_script = PROJECT_ROOT / "scripts" / "windows" / "setup_heygem.py"
    logger.warning(
        "已配置 HEYGEM_VIDEO_BASE_URL=%s，但服务不可达。\n"
        "  - 如已安装 Docker Desktop，请运行: python %s start\n"
        "  - 如未安装，请先运行: scripts\\windows\\安装HeyGem.bat\n"
        "  - 8003 将暂时以占位视频运行，等 Duix.Avatar 就绪后重启模型服务即可。",
        heygem_url,
        setup_script,
    )


def start_model_bridge_services(local_env: dict[str, str]) -> None:

    """启动 CosyVoice(8002)、HeyGem(8003) 与 TuiliONNX(8004) 包装服务。"""

    _ensure_cosyvoice_upstream_running()
    _ensure_heygem_upstream_running()

    cosyvoice_env = local_env.copy()

    for key in load_project_dotenv():

        if key.startswith("COSYVOICE_"):

            cosyvoice_env[key] = pick_env(key)

    if not _model_bridge_ready(

        "COSYVOICE",

        ("COSYVOICE_UPSTREAM_URL", "COSYVOICE_MODEL_DIR", "COSYVOICE_COMMAND_TEMPLATE"),

    ):

        cosyvoice_env["ALLOW_STUB_OUTPUT"] = "true"

        logger.info("CosyVoice 上游未配置，8002 将输出占位 WAV（可跑通 FFmpeg 链路）。")

    elif pick_env("ALLOW_MODEL_SERVICE_STUB_OUTPUT", "").lower() in ("1", "true", "yes"):

        cosyvoice_env["ALLOW_STUB_OUTPUT"] = "true"

        logger.info("已启用 ALLOW_MODEL_SERVICE_STUB_OUTPUT，8002 将输出占位 WAV。")



    heygem_env = local_env.copy()

    for key in load_project_dotenv():

        if key.startswith("HEYGEM_"):

            heygem_env[key] = pick_env(key)

    if not _model_bridge_ready(

        "HEYGEM",

        ("HEYGEM_UPSTREAM_URL", "HEYGEM_VIDEO_BASE_URL", "HEYGEM_COMMAND_TEMPLATE"),

    ):

        heygem_env["ALLOW_STUB_OUTPUT"] = "true"

        logger.info("HeyGem 上游未配置，8003 将输出占位视频（需本机已安装 ffmpeg）。")

    elif pick_env("ALLOW_MODEL_SERVICE_STUB_OUTPUT", "").lower() in ("1", "true", "yes"):

        heygem_env["ALLOW_STUB_OUTPUT"] = "true"

        logger.info("已启用 ALLOW_MODEL_SERVICE_STUB_OUTPUT，8003 将输出占位视频。")



    tuilionnx_env = local_env.copy()

    for key in load_project_dotenv():

        if key.startswith("TUILIONNX_"):

            tuilionnx_env[key] = pick_env(key)

    if not _model_bridge_ready(
        "TUILIONNX",
        ("TUILIONNX_UPSTREAM_URL", "TUILIONNX_REPO_PATH"),
    ):
        tuilionnx_env["ALLOW_STUB_OUTPUT"] = "true"
        logger.info("TuiliONNX 本地 ONNX 未配置，8004 将输出占位视频（需本机已安装 ffmpeg）。")
    elif pick_env("ALLOW_MODEL_SERVICE_STUB_OUTPUT", "").lower() in ("1", "true", "yes"):

        tuilionnx_env["ALLOW_STUB_OUTPUT"] = "true"

        logger.info("已启用 ALLOW_MODEL_SERVICE_STUB_OUTPUT，8004 将输出占位视频。")



    if COSYVOICE_SERVICE_DIR.exists():
        cosyvoice_python = (
            str(COSYVOICE_VENV_PYTHON)
            if COSYVOICE_VENV_PYTHON.exists() and pick_env("COSYVOICE_MODEL_DIR")
            else sys.executable
        )
        if cosyvoice_python != sys.executable:
            logger.info("CosyVoice 本地模型模式，8002 使用独立 venv: %s", cosyvoice_python)

        start_local_process(

            "cosyvoice",

            [cosyvoice_python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8002"],

            COSYVOICE_SERVICE_DIR,

            cosyvoice_env,

        )

    if HEYGEM_SERVICE_DIR.exists():

        start_local_process(

            "heygem",

            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8003"],

            HEYGEM_SERVICE_DIR,

            heygem_env,

        )

    if TUILIONNX_SERVICE_DIR.exists():
        tuilionnx_python = (
            str(TUILIONNX_VENV_PYTHON)
            if TUILIONNX_VENV_PYTHON.exists() and pick_env("TUILIONNX_REPO_PATH")
            else sys.executable
        )
        if tuilionnx_python != sys.executable:
            logger.info("TuiliONNX 本地 ONNX 模式，8004 使用独立 venv: %s", tuilionnx_python)

        start_local_process(
            "tuilionnx",
            [tuilionnx_python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8004"],
            TUILIONNX_SERVICE_DIR,
            tuilionnx_env,
        )





def start_local_services(local_env: dict[str, str]) -> None:

    """启动 API、模型包装服务与前端开发服务。"""

    if pick_env("USE_STUB_MODEL_ADAPTERS", "false").lower() != "true":

        start_model_bridge_services(local_env)

    start_local_process(

        "api",

        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],

        BACKEND_DIR,

        local_env,

    )

    npm = resolve_executable("npm")
    if npm is None:
        raise RuntimeError("未找到 npm，请先安装 Node.js 18+ 并加入 PATH。")
    start_local_process(
        "web",
        [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
        FRONTEND_DIR,
        local_env,
    )





def stop_local_services() -> None:

    """关闭所有本地子进程。"""

    for process in reversed(_local_processes):

        if process.poll() is not None:

            continue

        logger.info("停止进程 PID=%s", process.pid)

        process.terminate()

        try:

            process.wait(timeout=8)

        except subprocess.TimeoutExpired:

            process.kill()

    _local_processes.clear()





def wait_for_url(url: str, timeout_seconds: int = 120, interval: float = 2.0) -> bool:

    """轮询 URL 直到可访问。"""

    deadline = time.time() + timeout_seconds

    while time.time() < deadline:

        try:

            with request.urlopen(url, timeout=3) as response:

                if response.status == 200:

                    return True

        except URLError:

            pass

        time.sleep(interval)

    return False





def find_chrome() -> str | None:

    candidates = [

        os.environ.get("LOCALAPPDATA", "") + r"\Google\Chrome\Application\chrome.exe",

        r"C:\Program Files\Google\Chrome\Application\chrome.exe",

        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",

    ]

    for path in candidates:

        if path and os.path.exists(path):

            return path

    return None





def start_chrome_debug_background() -> None:

    """后台启动 Chrome 调试端口，供 Playwright 发布使用（不用于展示 UI）。"""

    chrome = find_chrome()

    if not chrome:

        logger.warning("未找到 Chrome，多平台自动发布可能不可用；UI 不受影响。")

        return

    user_data = os.path.join(os.environ.get("TEMP", str(PROJECT_ROOT)), "DigitalHuman_ChromeDebug")

    os.makedirs(user_data, exist_ok=True)

    cmd = [

        chrome,

        "--remote-debugging-port=9222",

        f"--user-data-dir={user_data}",

        "--no-first-run",

        "--no-default-browser-check",

        "--window-size=1,1",

        "--window-position=9999,9999",

        "about:blank",

    ]

    try:

        subprocess.Popen(

            cmd,

            stdout=subprocess.DEVNULL,

            stderr=subprocess.DEVNULL,

            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),

        )

        logger.info("已后台启动 Chrome 调试端口 9222（仅用于平台发布）。")

    except OSError as exc:

        logger.warning("Chrome 调试端口启动失败: %s", exc)





def open_desktop_window() -> None:

    """打开原生桌面窗口，加载现有 Web 前端（样式不变）。"""

    import webview



    logger.info("打开桌面窗口: %s", WEB_URL)

    webview.create_window(

        WINDOW_TITLE,

        WEB_URL,

        width=WINDOW_WIDTH,

        height=WINDOW_HEIGHT,

        min_size=(1100, 720),

        resizable=True,

        text_select=True,

    )

    webview.start(gui="edgechromium", debug=False)





def main() -> None:
    refresh_path()
    os.chdir(PROJECT_ROOT)

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    (STORAGE_DIR / "music").mkdir(parents=True, exist_ok=True)



    atexit.register(stop_local_services)



    local_env = build_local_env()

    sync_dotenv(local_env)



    ensure_desktop_deps()

    ensure_backend_deps()

    ensure_frontend_deps()

    if pick_env("USE_STUB_MODEL_ADAPTERS", "false").lower() != "true":

        ensure_model_service_deps()

    run_migrations(local_env)

    start_local_services(local_env)



    if pick_env("USE_STUB_MODEL_ADAPTERS", "false").lower() != "true":

        logger.info("等待 CosyVoice 包装服务...")

        if not wait_for_url("http://127.0.0.1:8002/health", timeout_seconds=45):

            logger.warning("CosyVoice 包装服务未就绪，生成配音可能失败，请查看 %s", LOG_DIR / "cosyvoice.log")



    logger.info("等待 API 就绪...")

    if not wait_for_url(API_HEALTH_URL, timeout_seconds=120):

        stop_local_services()

        raise RuntimeError(f"API 未就绪，请查看 {LOG_DIR / 'api.log'}")



    logger.info("等待前端就绪...")

    if not wait_for_url(WEB_URL.rsplit("/", 1)[0] + "/", timeout_seconds=120):

        stop_local_services()

        raise RuntimeError(f"前端未就绪，请查看 {LOG_DIR / 'web.log'}")



    chrome_thread = threading.Thread(target=start_chrome_debug_background, daemon=True)

    chrome_thread.start()



    try:

        open_desktop_window()

    finally:

        stop_local_services()





if __name__ == "__main__":

    try:

        main()

    except Exception as exc:
        logger.error("%s", exc)
        if sys.stdin.isatty():
            input("按 Enter 键退出...")
        sys.exit(1)


