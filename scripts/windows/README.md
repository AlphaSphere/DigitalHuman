# 数字人追爆 · Windows 本地桌面客户端

与 [KrLongAI](https://github.com/fa1314/KrLongAI) 一致：**本地桌面客户端**，不用 Docker、不用浏览器标签页。

## 使用方式

1. 安装 **Python 3.11+**、**Node.js 18+**
2. 真实视频文案识别需安装 **FFmpeg**、**yt-dlp**、**openai-whisper**（启动器会检测并在文案页提示）
3. 双击运行：

```
scripts/windows/一键启动数字人追爆.bat
```

4. 会自动：
   - 安装/更新 Python 后端依赖与 npm 前端依赖（首次较慢）
   - 使用 **SQLite**（`storage/digital_human.db`），无需 MySQL
   - **Celery 同步模式**，无需 Redis / 独立 Worker
   - 本地启动 API `:8000` 与 Vite `:5173`
   - 后台 Chrome `:9222`（仅 Playwright 发布，非 UI）
   - **pywebview 原生窗口** 打开创建任务页

## 样式说明

界面仍是现有 React 与 `Frontend/src/styles/app.css`，**视觉样式不变**，只是交付形态为桌面窗口。

## 依赖文件

| 文件 | 说明 |
|------|------|
| `requirements-desktop.txt` | pywebview |
| `.env.local.example` | 本地模式环境变量模板 |
| `storage/logs/api.log` / `web.log` | 启动失败时查看 |

## 环境变量（可选）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DESKTOP_WEB_URL` | `http://127.0.0.1:5173/tasks/new` | 桌面窗口入口 |
| `USE_STUB_MODEL_ADAPTERS` | `false` | `true` 仅返回约 60 字示例文案；识别真实口播请保持 `false` 并安装依赖 |
| `ALLOW_MODEL_SERVICE_STUB_OUTPUT` | `false` | `true` 时 8002/8003/8004 输出占位音视频；真实 AI 请设为 `false` |
| `COSYVOICE_UPSTREAM_URL` | 空 | 设为 `http://127.0.0.1:50000` 启用真实 CosyVoice 配音（先运行 `安装CosyVoice.bat`） |
| `HEYGEM_VIDEO_BASE_URL` | 空 | 设为 `http://127.0.0.1:8383` 启用 HeyGem 数字人口型（需 Docker） |

## 真实 AI 快速启用

1. 双击 `scripts/windows/安装CosyVoice.bat`（首次会下载约 2GB 模型）
2. 确认 `.env` 中 `ALLOW_MODEL_SERVICE_STUB_OUTPUT=false` 且 `COSYVOICE_UPSTREAM_URL=http://127.0.0.1:50000`
3. 运行 `scripts/windows/重启模型服务.bat`，配置页应显示 CosyVoice（8002）为 **upstream-http**
4. **数字人口型**：配置页选「上传自拍视频」即可先用真实配音；口型驱动需另行安装 Docker + [Duix.Avatar](https://github.com/duixcom/Duix-Avatar)

## 与 Docker 模式区别

| 模式 | 入口 | 适用 |
|------|------|------|
| **本地桌面（默认）** | `.bat` / `combined_launcher.py` | 日常使用，对齐 KrLongAI |
| Docker Compose | `docker compose up` | 团队部署 / 生产 |

## 常见问题

- **API 未就绪**：查看 `storage/logs/api.log`
- **前端未就绪**：查看 `storage/logs/web.log`，确认 5173 端口未被占用
- **多平台发布**：需本机安装 Chrome；首次 Playwright 可能需 `playwright install chromium`
