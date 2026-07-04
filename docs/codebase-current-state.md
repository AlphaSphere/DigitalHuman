# 代码架构与业务架构现状（As-Built，2026-07-04）

本文档基于对当前代码库的直接读取生成，记录**代码里实际存在的东西**，不代表设计意图。设计层面的目标、原则、备选方案见 [`technical-architecture.md`](technical-architecture.md)；本文只做现状核对，末尾标注与设计文档的主要差异。

对应代码版本：`main` @ `6248aef`（加速 KrLongAI 对齐）。

## 1. 顶层结构

```text
DigitalHuman/
  Backend/    FastAPI + Celery，Python
  Frontend/   React + TS + Vite
  Services/   7 个模型桥接微服务（部分已实现，部分是空目录）
  docker-compose.yml
  docs/
  storage/tasks/{task_id}/...
```

## 2. Backend

### 2.1 API 路由（`Backend/app/api/routers/`，10 个文件）

| 文件 | 主要路径 | 职责 |
| --- | --- | --- |
| `tasks.py` | `POST /tasks/video`、`/tasks/script`、`/tasks/{id}/*`、`GET /tasks/{id}` | 任务创建与基础读写 |
| `pipelines.py` | `GET /tasks`、`POST /tasks/batch`、`POST /pipelines/one-click`、`GET /tasks/{id}/pipeline-status` | 一键流水线入口与列表 |
| `segments.py` | `GET/PUT /tasks/{id}/segments`、`POST /tasks/{id}/check-script-risk`、`/confirm-script` | 文案片段编辑、确认 |
| `risk_checks.py` | `GET /tasks/{id}/risk-checks`、`POST .../confirm`、`POST /tasks/{id}/pre-publish-check` | 风险审核查询与人工确认 |
| `artifacts.py` | `GET /tasks/{id}/artifacts`、`GET /artifacts/{id}/download` | 产物列表与下载 |
| `covers.py` | `GET .../covers/candidates`、`POST .../covers/generate`、`/upload` | 封面生成/上传 |
| `distributions.py` | `GET/POST /tasks/{id}/distributions`、`.../batch`、`POST /distributions/{id}/retry` | 分发记录管理 |
| `profiles.py` | `GET /voice-profiles`、`/avatar-profiles` | 音色/数字人配置列表 |
| `music.py` | `GET /music-tracks`、`POST /music-tracks/upload` | 背景音乐库 |
| `system.py` | `GET /system/runtime-info` | 运行时信息（模型服务状态等） |

### 2.2 Service 层（`Backend/app/services/`，11 个模块）

`task_service`（任务 CRUD）、`pipeline_service`（编排）、`task_guards`（状态守卫）、`risk_service`、`segment_service`、`rewrite_service`（DeepSeek 仿写）、`distribution_service`、`cover_service`、`music_service`、`storage_service`、`profile_service`、`serializers`、`script_parser`、`id_service`。

### 2.3 Adapter 层（`Backend/app/adapters/`，10 个适配器）

| 适配器 | 关键方法 | 说明 |
| --- | --- | --- |
| `whisper.py` | `transcribe(source_video_path, task_id)` | ASR，HTTP 或 CLI |
| `cozyvoice.py` | `synthesize(task_id, text, voice_profile_id, ...)` | TTS |
| `heygem.py` | `generate_avatar_video(task_id, audio_path, ...)` | 数字人（官方引擎） |
| `tuilionnx.py` | `generate_avatar_video(task_id, audio_path, ..., sync_offset)` | 数字人（第二引擎，本地 ONNX） |
| `ffmpeg.py` | `extract_audio`、`generate_subtitle`、`compose_final`、`extract_frame`、`probe_duration` | 音视频处理 |
| `distributor.py` | `upload_video(task_id, video_path, platform, ...)` | sau CLI 分发 |
| `url_download.py` | `is_remote_url`、`download(task_id, url)` | yt-dlp 对标下载 |
| `llm.py`（DeepSeekAdapter） | `rewrite_script`、`generate_publish_metadata`、`check_script_compliance`、`generate_cover_copy` | 文案仿写/合规/元信息/封面文案 |
| `cover.py` | `extract_frame_candidates`、`generate_cover` | 封面抽帧 + 合成 |
| `playwright_publisher.py` | `upload_video(...)` | 浏览器发布（备用通道） |

### 2.4 Workers（`Backend/app/workers/tasks.py`，Celery）

- `transcribe_video_task(task_id)`：下载（如为 URL）→ 抽音频 → Whisper 识别 → 写 `script_segments`
- `run_generation_pipeline(task_id)`：配音（CozyVoice）→ 数字人（HeyGem/TuiliONNX）→ 字幕（FFmpeg）→ 合成（FFmpeg）
- `run_full_pipeline_task(task_id, options)`：一键流程，见第 6 节
- `generate_cover_task`、`run_distribution_task`、`run_batch_distribution_task`

### 2.5 状态机（`Backend/app/domain/enums.py` → `TaskStatus`）

```
uploaded → audio_extracted → transcribing → transcribed
script_pasted → script_parsing → script_parsed
  → script_confirmed → content_checking
    → content_review_required / content_rejected
    → dubbing → dubbed → avatar_generating → avatar_generated
    → subtitle_generating → composing → completed
    → publish_checking → publish_blocked / publish_ready
(任意生成阶段) → failed → retrying
```

守卫逻辑在 `task_guards.py`：`GENERATION_PHASE_STATUSES`（生成阶段禁止改文案）、`PRE_GENERATION_EDITABLE_STATUSES`、`SCRIPT_RISK_CONFIRM_STATUSES`，另有 `assert_can_retry_generation`、`is_stale_generation`（15 分钟判定超时）。

共 21 个枚举（`domain/enums.py`），覆盖任务状态、文案来源、产物类型、画幅、生成质量、风险等级/类型、授权来源等。

### 2.6 数据库模型（`Backend/app/db/models.py`，8 张表）

`TaskModel`、`ScriptSegmentModel`、`ArtifactModel`、`VoiceProfileModel`、`AvatarProfileModel`、`RiskCheckModel`、`RiskFindingModel`、`AuthorizationRecordModel`、`DistributionRecordModel`（共 9 个模型类，对应上述含 RiskFinding）。

## 3. Frontend

### 3.1 路由（`Frontend/src/routes/AppRoutes.tsx`）

| 路径 | 页面 |
| --- | --- |
| `/` | 重定向到 `/tasks/new` |
| `/quick` | QuickPipelinePage（一键入口） |
| `/tasks` | TaskListPage |
| `/tasks/new` | NewTaskPage |
| `/tasks/:taskId/script` | ScriptPage |
| `/tasks/:taskId/risk-review` | RiskReviewPage |
| `/tasks/:taskId/config` | ConfigPage |
| `/tasks/:taskId/progress` | ProgressPage |
| `/tasks/:taskId/pipeline` | TaskFlowRedirect |
| `/tasks/:taskId/pipeline-progress` | PipelineProgressPage |
| `/tasks/:taskId/result` | ResultPage |
| `/tasks/:taskId/pre-publish` | PrePublishPage |

组件层（`src/components/`）约 20 个，覆盖风险审核（RiskCard/RiskSummary/ScriptRiskPanel）、生成失败展示（GenerationFailureModal/Details）、字幕/BGM/语速控件等。`src/lib/api-client/mockApi.ts` 是当前唯一的 API client 实现（**没有真实后端 HTTP client**，页面通过 fetch/mock 交互，需要核实是否已切换到真实接口）。

## 4. Services 微服务现状

| 服务 | 状态 | 接入模式 |
| --- | --- | --- |
| `whisper-service` | **真实实现** | 本地 openai-whisper 模型推理 |
| `cosyvoice-service` | **真实实现** | 官方 FastAPI / 本地 CLI / 模型目录三种模式 + stub |
| `heygem-service` | **真实实现** | 官方 Video API（`/easy/submit`+轮询）/ CLI / stub |
| `tuilionnx-service` | **真实实现** | 本地 ONNX 推理（Ultralight-Digital-Human）/ HTTP / stub |
| `faster-whisper-service` | **空壳** | 目录存在，无 `app/main.py`，未接入 Backend |
| `wav2lip-service` | **空壳** | 同上 |
| `xtts-service` | **空壳** | 同上 |
| `distributor`（compose 里） | **占位** | 容器仅 `sleep infinity`，需手动装 sau CLI |

统一开关：`Backend/app/core/config.py` 的 `use_stub_model_adapters`（默认 `True`），为 `False` 时才会真正调用上游模型服务，否则各适配器返回占位产物（静音 wav / 黑底 mp4）。

## 5. Docker Compose 服务清单

| 服务 | 端口 | profile |
| --- | --- | --- |
| web | 5173 | — |
| api | 8000 | — |
| worker | — | — |
| mysql | 3306 | — |
| redis | 6379 | — |
| whisper | 8001 | `whisper` / `models` |
| cosyvoice | 8002 | `cosyvoice` / `models` |
| heygem | 8003 | `heygem` / `models` |
| tuilionnx | 8004 | `tuilionnx` / `models` |
| distributor | — | `distribution` |

## 6. 一键生成业务流程（`run_full_pipeline_task`）

```
1. 转写：下载(如URL) → 抽音频 → Whisper → script_segments
2. 仿写（可选，options.rewrite_enabled）：DeepSeek 改写 edited_text
3. 风险审核：DeepSeek 合规检查
     blocked        → content_rejected（终止）
     passed         → 自动 confirm，进入生成
     warning/manual → content_review_required（等待人工确认）
4. 生成（脚本已确认后）：
     配音 CozyVoice → 数字人 HeyGem/TuiliONNX → 字幕 FFmpeg → 合成 FFmpeg（含 BGM）
5. 封面（可选）：CoverAdapter 抽帧 + DeepSeek 文案
6. 元信息（可选）：DeepSeek 生成标题/简介/标签
7. 分发（可选，需元信息就绪）：批量投递各平台任务
```

## 7. 鉴权现状

**当前没有生效的鉴权机制**：`app/api/deps.py` 只提供 `get_db`，`main.py` 未注册任何认证中间件，所有路由仅做 `Depends(get_db)`。此前一次重构中出现过的 `auth.py`/`auth_service.py`/`LoginModal.tsx`/Google OAuth 等文件，在 2026-07-01 的 `git reset --hard` 中已被丢弃（未合并入远程主分支）。**所有 API 目前对外公开、无身份校验**——如果要部署到非本地/非内网环境，这是需要优先处理的安全缺口。

## 8. 与 `technical-architecture.md` 的主要差异

- 设计文档以 `Whisper/CozyVoice/HeyGem` 三个模型服务为主线；代码中已新增 **TuiliONNX** 作为第二数字人引擎（文档第 17 节有提及，基本同步），但 `faster-whisper/wav2lip/xtts` 三个服务目录只是脚手架，尚未实现。
- 设计文档未讨论鉴权；实际代码目前无任何鉴权层（见第 7 节）。
- 设计文档中的分层建议（`repositories/`）在当前代码里未独立成目录，数据访问逻辑直接写在 `services/` 内。
- Frontend 的真实 API 对接情况需要再核实 `mockApi.ts` 是否已被替换/停用——如果生产环境仍在用 mock，前后端联调状态和文档描述可能不一致。
