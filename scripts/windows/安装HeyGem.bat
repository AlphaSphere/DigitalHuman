@echo off
chcp 65001 >nul
cd /d "%~dp0..\.."
echo ========================================
echo   安装 HeyGem / Duix.Avatar 数字人服务
echo   前提：已安装 Docker Desktop 并运行
echo   首次拉取镜像约 70GB，请确保磁盘充足
echo ========================================
echo.
python scripts/windows/setup_heygem.py install
if errorlevel 1 (
    echo.
    echo [错误] 安装失败，请查看上方错误信息。
    echo 常见原因：
    echo   1. Docker Desktop 未启动，请打开后重试
    echo   2. 网络问题，请检查是否可访问 hub.docker.com
    echo   3. 磁盘空间不足（需约 70GB）
    pause
    exit /b 1
)
echo.
echo 然后运行 scripts\windows\重启模型服务.bat 使配置生效
pause
