# 启动桌面客户端（内部会启动 Docker + 原生窗口）
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root
python (Join-Path $PSScriptRoot "combined_launcher.py")
