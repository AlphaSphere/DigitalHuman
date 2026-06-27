@echo off
chcp 65001 >nul
echo === DigitalHuman 模型包装服务健康检查 ===
echo.

for %%P in (8002:CosyVoice 8003:HeyGem 8004:TuiliONNX) do (
  for /f "tokens=1,2 delims=:" %%A in ("%%P") do (
    echo [%%B :%%A]
    curl -s http://127.0.0.1:%%A/health
    echo.
    echo.
  )
)

echo 若返回空或连接失败，请重新运行「一键启动数字人追爆.bat」。
echo 真实 AI 配音/数字人需在 .env 配置 COSYVOICE_UPSTREAM_URL / HEYGEM_VIDEO_BASE_URL 等。
pause
