@echo off
chcp 65001 >nul
title 重启 DigitalHuman 本地服务

cd /d "%~dp0\..\.."

echo ========================================
echo  重启 API / 模型服务 / 前端
echo ========================================

python "%~dp0restart_all_dev.py"
if errorlevel 1 (
  echo 重启失败，请查看 storage\logs\
  pause
  exit /b 1
)

echo.
echo 已就绪：http://127.0.0.1:5173/
pause
