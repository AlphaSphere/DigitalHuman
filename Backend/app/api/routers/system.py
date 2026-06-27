"""系统运行信息（前端展示 Stub/依赖状态）。"""

import os
from shutil import which

import httpx
from fastapi import APIRouter

from app.core.config import get_settings
from app.core.exceptions import success_response
from app.services.risk_service import resolve_script_risk_check_mode

router = APIRouter()


def _refresh_path_for_detection() -> None:
    """Windows 下合并最新 PATH，避免刚安装的 ffmpeg/yt-dlp 检测不到。"""
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


def _has_command(name: str) -> bool:
    _refresh_path_for_detection()
    return which(name) is not None


def _probe_model_service(base_url: str) -> dict:
    """探测模型包装服务 /health。"""
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/health", timeout=2.5)
        if response.status_code != 200:
            return {"ok": False, "mode": None}
        payload = response.json()
        return {"ok": True, "mode": payload.get("mode")}
    except Exception:
        return {"ok": False, "mode": None}


@router.get("/system/runtime-info")
def runtime_info() -> dict:
    """返回当前运行模式与 ASR/模型/合规依赖是否可用。"""
    settings = get_settings()
    cosyvoice = _probe_model_service(settings.cozyvoice_base_url)
    heygem = _probe_model_service(settings.heygem_base_url)
    tuilionnx = _probe_model_service(settings.tuilionnx_base_url)
    return success_response(
        {
            "use_stub_model_adapters": settings.use_stub_model_adapters,
            "enable_url_import": settings.enable_url_import,
            "has_yt_dlp": _has_command(settings.url_download_command),
            "has_ffmpeg": _has_command(settings.ffmpeg_command),
            "has_whisper_cli": _has_command(settings.whisper_command),
            "whisper_base_url": settings.whisper_base_url or None,
            "enable_llm_rewrite": settings.enable_llm_rewrite,
            "has_deepseek_api_key": bool(settings.deepseek_api_key),
            "deepseek_model": settings.deepseek_model,
            "deepseek_base_url": settings.deepseek_base_url,
            "risk_check_mode": resolve_script_risk_check_mode(),
            "cosyvoice_ok": cosyvoice["ok"],
            "cosyvoice_mode": cosyvoice["mode"],
            "heygem_ok": heygem["ok"],
            "heygem_mode": heygem["mode"],
            "tuilionnx_ok": tuilionnx["ok"],
            "tuilionnx_mode": tuilionnx["mode"],
        }
    )
