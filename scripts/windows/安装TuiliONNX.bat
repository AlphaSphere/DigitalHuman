@echo off
chcp 65001 >nul
cd /d "%~dp0..\.."
echo ========================================
echo   安装 TuiliONNX / ONNX 数字人推理
echo   基于 Ultralight-Digital-Human
echo   需要：Python 3.11+、Git、ffmpeg、NVIDIA GPU（推荐）
echo ========================================
echo.
python scripts/windows/setup_tuilionnx.py install
if errorlevel 1 (
    echo.
    echo [错误] 安装失败，请查看上方错误信息。
    pause
    exit /b 1
)
echo.
echo 安装完成后请运行 scripts\windows\重启模型服务.bat
echo 若需训练专属数字人，再运行：
echo   python scripts/windows/setup_tuilionnx.py prepare --video 你的口播视频.mp4
pause
