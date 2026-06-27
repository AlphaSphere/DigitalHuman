@echo off
chcp 65001 >nul
title 重启模型包装服务（方案A占位模式）
cd /d "%~dp0\..\.."
python "%~dp0restart_model_bridge.py"
if errorlevel 1 pause
