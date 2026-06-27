@echo off

chcp 65001 >nul

title DigitalHuman 桌面客户端

cd /d "%~dp0\..\.."



echo ========================================

echo  数字人追爆 · 本地桌面客户端

echo  无需 Docker，原生窗口运行

echo ========================================

echo.



where python >nul 2>&1

if errorlevel 1 (

  echo 未找到 Python，请先安装 Python 3.11+ 并加入 PATH。

  pause

  exit /b 1

)



where npm >nul 2>&1

if errorlevel 1 (

  echo 未找到 npm，请先安装 Node.js 18+ 并加入 PATH。

  pause

  exit /b 1

)



python "%~dp0combined_launcher.py"

if errorlevel 1 (

  echo 桌面客户端启动失败，日志见 storage\logs\

  pause

  exit /b 1

)


