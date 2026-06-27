@echo off
chcp 65001 >nul
cd /d "%~dp0..\.."
echo ========================================
echo   安装 CosyVoice 真实 AI 配音（GPU）
echo   首次约需 5-15 分钟（含模型下载）
echo ========================================
python scripts/windows/setup_cosyvoice.py install
if errorlevel 1 exit /b 1
python scripts/windows/setup_cosyvoice.py start
if errorlevel 1 exit /b 1
echo.
echo 请在 .env 中确认：
echo   ALLOW_MODEL_SERVICE_STUB_OUTPUT=false
echo   COSYVOICE_UPSTREAM_URL=http://127.0.0.1:50000
echo 然后运行 scripts/windows/重启模型服务.bat
pause
