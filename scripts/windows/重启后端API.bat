@echo off
chcp 65001 >nul
title 重启后端 API（8000）
cd /d "%~dp0\..\.."
python "%~dp0restart_api.py"
if errorlevel 1 pause
