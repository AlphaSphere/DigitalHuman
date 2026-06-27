# 数字人视频生成项目前后端 API 接口文档

## 1. 文档说明

本文档从 `docs/technical-architecture.md` 中抽离 API 相关内容，作为前端页面、后端 FastAPI 路由和联调测试的接口依据。

API 服务只负责参数校验、任务状态管理、文件路径记录和异步任务投递，不直接执行 Whisper、CozyVoice、HeyGem、FFmpeg 等长耗时任务。生成进度通过任务状态查询接口返回给前端。

## 2. 前后端调用总览

### 2.1 上传视频自动识别流程

```mermaid
sequenceDiagram
  participant User as 用户
  participant Web as Web前端
  participant API as API服务
  participant Queue as 任务队列
  participant Worker as 生成Worker
  participant Storage as 文件存储

  User->>Web: 上传参考视频
  Web->>API: POST /api/tasks/video
  API->>Storage: 保存 source.mp4
  API->>Queue: 投递 ASR 任务
  API-->>Web: 返回 task_id 和 uploaded 状态
  Web->>API: GET /api/tasks/{task_id}
  Worker->>Storage: 保存 whisper_segments.json
  Worker->>API: 更新状态为 transcribed
  Web->>API: GET /api/tasks/{task_id}/segments
  User->>Web: 编辑并确认文案
  Web->>API: PUT /api/tasks/{task_id}/segments
  Web->>API: POST /api/tasks/{task_id}/confirm-script
  Web->>API: GET /api/tasks/{task_id}/risk-checks?stage=script
  User->>Web: 必要时人工确认风险
  Web->>API: POST /api/tasks/{task_id}/generation-config
  Web->>API: POST /api/tasks/{task_id}/generate
  API->>Queue: 投递生成任务
  Web->>API: 轮询 GET /api/tasks/{task_id}
  Worker->>Storage: 保存最终视频
  Worker->>API: 更新状态为 completed
  Web->>API: GET /api/tasks/{task_id}/artifacts
  Web->>API: GET /api/artifacts/{artifact_id}/download
```

### 2.2 粘贴字幕 / 文案流程

```mermaid
sequenceDiagram
  participant User as 用户
  participant Web as Web前端
  participant API as API服务
  participant Queue as 任务队列
  participant Worker as 生成Worker
  participant Storage as 文件存储

  User->>Web: 粘贴字幕或文案
  Web->>API: POST /api/tasks/script
  API->>Storage: 保存 pasted_script.txt
  API->>Queue: 投递解析任务
  API-->>Web: 返回 task_id 和 script_pasted 状态
  Worker->>Storage: 保存 parsed_segments.json
  Worker->>API: 更新状态为 script_parsed
  Web->>API: GET /api/tasks/{task_id}/segments
  User->>Web: 选择完整文案或分段时间轴并确认文案
  Web->>API: PUT /api/tasks/{task_id}/segments
  Web->>API: POST /api/tasks/{task_id}/confirm-script
  Web->>API: GET /api/tasks/{task_id}/risk-checks?stage=script
  User->>Web: 必要时人工确认风险
  Web->>API: POST /api/tasks/{task_id}/generation-config
  Web->>API: POST /api/tasks/{task_id}/generate
  Web->>API: 轮询 GET /api/tasks/{task_id}
  Worker->>Storage: 保存最终视频
  Worker->>API: 更新状态为 completed
```

## 3. 通用约定

### 3.1 Base URL

MVP 本地开发：

```text
http://localhost:8000
```

接口统一以 `/api` 开头。

### 3.2 请求格式

- 普通 JSON 接口使用 `Content-Type: application/json`。
- 上传参考视频接口使用 `multipart/form-data`。
- 配置页如果同时上传自定义音色样本或自拍视频，`generation-config` 可以使用 `multipart/form-data`；如果文件已先上传到素材存储，也可以用 JSON 传 `custom_voice_file_name` / `custom_video_file_name` 或后续扩展的素材 ID。
- 下载接口由后端返回文件流或短期有效下载链接。

### 3.3 通用响应格式

成功响应：

```json
{
  "success": true,
  "data": {}
}
```

失败响应：

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "上传文件格式不支持",
    "detail": {}
  }
}
```

实现注意：

- `message` 面向用户展示，必须是简短中文说明。
- `detail` 只放非敏感排查信息，不返回内部命令、token、完整系统路径。
- 前端判断业务失败优先读取 `error.code`，展示文案读取 `error.message`。

### 3.4 通用状态码

| HTTP 状态码 | 使用场景 |
| --- | --- |
| `200` | 查询或更新成功。 |
| `201` | 创建任务成功。 |
| `202` | 已接受异步处理请求。 |
| `400` | 参数格式错误、状态不允许、文件不合法。 |
| `403` | 当前用户无权访问任务或产物，账号系统接入后启用。 |
| `404` | 任务、段落、产物不存在。 |
| `409` | 当前任务状态不允许执行该操作。 |
| `413` | 上传文件或文本过大。 |
| `500` | 服务端未预期错误。 |

### 3.5 鉴权预留

MVP 可以先不启用账号系统。后续接入多用户时建议：

- 使用 `Authorization: Bearer <token>`。
- 所有 `task_id`、`artifact_id` 查询必须校验归属用户。
- 下载链接使用短期签名，避免长期暴露文件路径。

## 4. 数据结构

### 4.1 Task

```json
{
  "id": "task_01HZX...",
  "script_source": "video_asr",
  "script_generation_mode": "full_script",
  "status": "transcribed",
  "source_video_path": "storage/tasks/task_01HZX/input/source.mp4",
  "duration": 62.5,
  "aspect_ratio": "9:16",
  "generation_voice_mode": "uploaded_voice",
  "custom_voice_path": "storage/tasks/task_01HZX/input/voice_sample.wav",
  "generation_video_mode": "uploaded_video",
  "custom_video_path": "storage/tasks/task_01HZX/input/self_video.mp4",
  "voice_profile_id": "voice_default",
  "avatar_profile_id": "avatar_default",
  "error_code": null,
  "error_message": null,
  "created_at": "2026-06-01T06:30:00Z",
  "updated_at": "2026-06-01T06:35:00Z"
}
```

### 4.2 ScriptSegment

```json
{
  "id": "seg_001",
  "task_id": "task_01HZX...",
  "index": 1,
  "source_type": "whisper",
  "start_time": 0.0,
  "end_time": 4.2,
  "original_text": "大家好，今天介绍一个数字人口播流程。",
  "edited_text": "大家好，今天介绍一个数字人口播视频生成流程。",
  "confidence": 0.94
}
```

### 4.3 Artifact

```json
{
  "id": "artifact_final_video",
  "task_id": "task_01HZX...",
  "type": "final_video",
  "path": "storage/tasks/task_01HZX/output/final_with_subtitle.mp4",
  "meta": {
    "duration": 62.5,
    "format": "mp4",
    "size_bytes": 10485760
  },
  "created_at": "2026-06-01T06:50:00Z"
}
```

### 4.4 VoiceProfile

```json
{
  "id": "voice_default",
  "name": "默认中文女声",
  "provider": "cozyvoice",
  "sample_path": "storage/voices/default.wav",
  "config": {
    "speed": 1.0,
    "volume": 1.0
  }
}
```

### 4.5 AvatarProfile

```json
{
  "id": "avatar_default",
  "name": "默认数字人",
  "provider": "heygem",
  "config": {
    "resolution": "1080x1920",
    "template_path": "storage/avatars/default"
  }
}
```

### 4.6 RiskCheck

```json
{
  "id": "risk_01HZX...",
  "task_id": "task_01HZX...",
  "stage": "script",
  "risk_status": "warning",
  "risk_level": "medium",
  "risk_types": ["sensitive_keyword", "privacy"],
  "findings": [
    {
      "id": "finding_01HZX...",
      "type": "sensitive_keyword",
      "target": "script",
      "text": "命中的关键词或说明",
      "position": "第 3 段 / 00:12",
      "suggestion": "建议替换或删除该表述"
    }
  ],
  "reviewed_by": "system",
  "reviewed_at": null,
  "created_at": "2026-06-01T06:40:00Z"
}
```

### 4.7 AuthorizationRecord

```json
{
  "id": "auth_01HZX...",
  "task_id": "task_01HZX...",
  "asset_type": "voice",
  "source": "user_upload",
  "authorization_confirmed": true,
  "authorization_note": "用户确认拥有声音素材授权",
  "confirmed_at": "2026-06-01T06:31:00Z"
}
```

## 5. 后端路由建议

后端代码包位于 `Backend/`。FastAPI 路由建议按资源和页面流程拆分，避免所有接口堆在一个文件里。

| Router 文件 | 接口范围 | 主要依赖 Service |
| --- | --- | --- |
| `app/api/routers/tasks.py` | 创建任务、查询任务、启动生成、失败重试。 | `task_service.py`、`generation_service.py` |
| `app/api/routers/segments.py` | 获取、保存文案段落，运行脚本合规检查，确认文案。 | `segment_service.py` |
| `app/api/routers/profiles.py` | 获取音色列表、数字人列表。 | `task_service.py` 或独立 `profile_service.py` |
| `app/api/routers/artifacts.py` | 查询产物列表、下载产物。 | `artifact_service.py` |
| `app/api/routers/risk_checks.py` | 查询风险结果、人工确认风险、发布前合规检查。 | `risk_service.py` |
| `app/api/routers/music.py` | 查询 CC0 背景音乐素材。 | `music_service.py` |
| `app/api/routers/distributions.py` | 创建、查询和重试平台分发任务。 | `distribution_service.py` |

调用边界：

- Router 只负责 HTTP 入参、权限校验和响应封装，不直接操作数据库模型。
- Service 负责业务编排，例如创建任务、保存文案、投递 Celery 任务。
- Repository 负责 SQLAlchemy 查询，避免业务代码散落 SQL 细节。
- Worker 执行长耗时任务后，通过 Repository 更新任务状态和产物记录。

新增真实工具接入接口：

| 接口 | 用途 |
| --- | --- |
| `GET /api/music-tracks` | 返回后端本地 CC0-1.0 Music 音乐目录中的可选曲目。 |
| `POST /api/music-tracks/upload` | 上传用户自定义 BGM 文件（mp3/wav/m4a/aac/flac/ogg）到音乐库，返回新增曲目元数据。 |
| `POST /api/tasks/{task_id}/distributions` | 调用 social-auto-upload 创建平台分发任务。 |
| `GET /api/tasks/{task_id}/distributions` | 查询任务的分发记录和平台返回结果。 |
| `POST /api/distributions/{distribution_id}/retry` | 对失败的分发记录重新投递。 |

模型服务内部接口不暴露给前端，由 Worker 通过适配器调用：

| 服务 | 接口 | 请求核心字段 | 返回核心字段 |
| --- | --- | --- | --- |
| Whisper Service | `POST /transcribe` | `path`、`language`、`model` | `segments[]`，包含 `start_time`、`end_time`、`text`、`confidence` |
| CosyVoice Service | `POST /synthesize` | `task_id`、`text`、`voice_profile_id`、`custom_voice_path`、`custom_voice_prompt_text`、`output_path` | `audio_path` |
| HeyGem Service | `POST /generate` | `task_id`、`audio_path`、`avatar_profile_id`、`output_path` | `video_path` |
| TuiliONNX Service | `POST /generate` | 同 HeyGem + `compress_inference`、`sync_offset`、`inference_scale` | `video_path`、`synced_audio_path` |

真实生成配置说明：

- CosyVoice 官方 FastAPI 会返回原始 PCM 音频流，包装服务会转成标准 WAV 写入 `output_path`。
- `custom_voice_path` 存在时，若同时提供 `custom_voice_prompt_text`，CosyVoice 包装服务优先走 zero-shot；没有样本文本才退回 cross_lingual。没有自定义音色时使用 `voice_profile_id` 或 `COSYVOICE_SFT_SPK_ID` 作为预设音色。
- 后端对上传音色按约 **60 字/段** 切分后再串行合成；预设音色 SFT 可至 **180 字/段**。包装服务会将音色样本统一转为 16kHz 单声道 WAV，并截取前 **5 秒** 使用。
- `custom_voice_prompt_text` 可选；填写且与样本一致时优先 zero-shot，更快更稳；不填则退回 cross_lingual 克隆。
- 保存配置时若选择「默认音色」，后端会忽略误传的 `custom_voice_file`，避免配置写成 `preset_voice` 却仍保留上传样本导致合成走默认音色。
- HeyGem 官方接口（Duix.Avatar :8383）需要已有数字人视频素材，包装服务会优先把 `avatar_profile_id` 当作视频路径，其次读取 `HEYGEM_AVATAR_PROFILE_MAP`，最后使用 `HEYGEM_DEFAULT_VIDEO_PATH`。
- HeyGem 合成完成后，包装服务会优先从查询结果中解析视频路径；如果官方接口没有返回明确路径，则从 `HEYGEM_RESULT_DIR` 中按任务 code 查找输出 MP4。
- Duix.Avatar 运行在 Docker 容器中，无法直接读取宿主机 `C:\` 路径。通过 `HEYGEM_HOST_STORAGE_ROOT` / `HEYGEM_CONTAINER_STORAGE_ROOT` 配置路径映射，heygem-service 会在提交前自动翻译路径。容器启动时需 `-v <host_storage>:<container_storage>` 挂载 storage 目录。
- TuiliONNX 引擎使用 Ultralight-Digital-Human 本地 ONNX 推理（8004 `local-onnx` 模式）；需配置 `TUILIONNX_REPO_PATH` 与 `TUILIONNX_DEFAULT_DATA_PATH`。
- TuiliONNX 推理会额外输出 `avatar_synced_audio.wav`（与口型帧严格对齐的 16kHz 音频）；Worker 成片合成优先使用该文件，避免原始 TTS 与口型不同步。

## 6. 接口详情

### 6.1 上传视频并创建任务

```http
POST /api/tasks/video
```

用途：上传参考视频或提交公开链接，创建 ASR 任务。**接口会立即返回**（`status=uploaded`），下载/转写由后台 `transcribe_video_task` 异步执行；前端应在文案页轮询任务状态直至 `transcribed` 或 `failed`。

前端调用时机：任务创建页中，用户选择“上传视频”并提交后调用。

请求格式：`multipart/form-data`

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 二选一 | 参考视频文件，建议限制为 `mp4` / `mov`。 |
| `source_url` | string | 二选一 | 公开可访问的视频链接（http/https），后端用 yt-dlp 下载。 |
| `aspect_ratio` | string | 否 | 期望输出比例，例如 `9:16`。 |

响应示例：

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "task_01HZX...",
      "script_source": "video_asr",
      "status": "uploaded",
      "created_at": "2026-06-01T06:30:00Z",
      "updated_at": "2026-06-01T06:30:00Z"
    }
  }
}
```

常见错误：

- `VALIDATION_ERROR`：文件类型、大小或时长不符合要求。

### 6.2 粘贴字幕 / 文案并创建任务

```http
POST /api/tasks/script
```

用途：创建粘贴文案任务，后端保存原始文本并解析为统一的文案段落。

前端调用时机：任务创建页中，用户选择“粘贴字幕 / 文案”并提交后调用。

请求示例：

```json
{
  "content": "大家好，今天介绍一个数字人口播流程。",
  "content_type": "pasted_script",
  "aspect_ratio": "9:16"
}
```

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `content` | string | 是 | 用户粘贴的字幕或纯文案。 |
| `content_type` | enum | 是 | `pasted_subtitle` / `pasted_script`。 |
| `aspect_ratio` | string | 否 | 期望输出比例。 |

响应示例：

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "task_01HZT...",
      "script_source": "pasted_script",
      "status": "script_pasted",
      "created_at": "2026-06-01T06:30:00Z",
      "updated_at": "2026-06-01T06:30:00Z"
    }
  }
}
```

常见错误：

- `VALIDATION_ERROR`：文本为空、超过长度限制或 `content_type` 不合法。
- `SCRIPT_PARSE_FAILED`：字幕格式无法解析。

### 6.3 获取文案段落

```http
GET /api/tasks/{task_id}/segments
```

用途：获取 Whisper 识别或粘贴文案解析后的段落，供前端展示和编辑。

前端调用时机：任务进入 `transcribed` 或 `script_parsed` 后，文案确认页加载时调用。

响应示例：

```json
{
  "success": true,
  "data": {
    "segments": [
      {
        "id": "seg_001",
        "task_id": "task_01HZX...",
        "index": 1,
        "source_type": "whisper",
        "start_time": 0.0,
        "end_time": 4.2,
        "original_text": "大家好，今天介绍一个数字人口播流程。",
        "edited_text": null,
        "confidence": 0.94
      }
    ]
  }
}
```

常见错误：

- `404`：任务不存在。
- `409`：任务尚未完成识别或解析。

### 6.4 保存用户修改后的段落

```http
PUT /api/tasks/{task_id}/segments
```

用途：保存用户编辑后的文案、分段顺序和时间信息。

前端支持两种文案生成方式：

- `full_script`：默认模式，把完整原视频文案保存为一个文案段落，完整文本最多 5000 字。
- `timed_segments`：按时间点保存多个文案片段，保留 `start_time` / `end_time` 供字幕和视频节奏对齐。

前端调用时机：文案确认页中，用户点击保存或自动保存时调用。

请求示例：

```json
{
  "script_generation_mode": "timed_segments",
  "segments": [
    {
      "id": "seg_001",
      "index": 1,
      "start_time": 0.0,
      "end_time": 4.5,
      "edited_text": "大家好，今天介绍一个数字人口播视频生成流程。"
    }
  ]
}
```

完整文案模式请求示例：

```json
{
  "script_generation_mode": "full_script",
  "segments": [
    {
      "id": "seg_full_task_01HZX",
      "index": 1,
      "start_time": 0.0,
      "end_time": 62.5,
      "edited_text": "这里是完整原视频文案，最多 5000 字。"
    }
  ]
}
```

响应示例：

```json
{
  "success": true,
  "data": {
    "segments": [
      {
        "id": "seg_001",
        "index": 1,
        "edited_text": "大家好，今天介绍一个数字人口播视频生成流程。"
      }
    ]
  }
}
```

常见错误：

- `VALIDATION_ERROR`：段落为空、顺序重复、结束时间早于开始时间。
- `409`：任务已进入生成阶段，不允许继续修改文案。

### 6.5 文案合规检查（同页）

```http
POST /api/tasks/{task_id}/check-script-risk
```

用途：对当前已保存的文案段落调用 DeepSeek 执行 AI 合规扫描，返回 `task` 与 `riskCheck`（含字符位置，用于前端高亮标注）。

前端调用时机：用户在文案页完成 DeepSeek 仿写后自动触发，或手动点击「运行 AI 合规检查」（需已配置 `DEEPSEEK_API_KEY`）。

响应示例：

```json
{
  "success": true,
  "data": {
    "task": { "id": "task_01HZX...", "status": "content_review_required" },
    "riskCheck": { "id": "risk_01...", "risk_status": "warning", "findings": [] }
  }
}
```

### 6.6 确认最终文案

```http
POST /api/tasks/{task_id}/confirm-script
```

用途：合规检查通过且用户点击「继续配置生成」时，将任务状态更新为 `script_confirmed`（内部会再次校验文案风险）。若需人工确认的风险，应调用 `POST /api/tasks/{task_id}/risk-checks/{id}/confirm`。

前端调用时机：文案页合规检查通过后，用户确认进入配置页前调用。

请求示例：

```json
{
  "confirmed": true
}
```

响应示例：

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "task_01HZX...",
      "status": "script_confirmed",
      "updated_at": "2026-06-01T06:40:00Z"
    }
  }
}
```

常见错误：

- `409`：任务尚未完成识别 / 解析，或没有可确认的文案段落。

### 6.7 获取音色列表

```http
GET /api/voice-profiles
```

用途：获取可选音色列表。

前端调用时机：配音与数字人配置页加载时调用。

响应示例：

```json
{
  "success": true,
  "data": {
    "voice_profiles": [
      {
        "id": "voice_default",
        "name": "默认中文女声",
        "provider": "cozyvoice",
        "sample_path": "storage/voices/default.wav",
        "config": {
          "speed": 1.0,
          "volume": 1.0
        }
      }
    ]
  }
}
```

### 6.7 获取数字人列表

```http
GET /api/avatar-profiles
```

用途：获取可选数字人列表。

前端调用时机：配音与数字人配置页加载时调用。

响应示例：

```json
{
  "success": true,
  "data": {
    "avatar_profiles": [
      {
        "id": "avatar_default",
        "name": "默认数字人",
        "provider": "heygem",
        "config": {
          "resolution": "1080x1920",
          "template_path": "storage/avatars/default"
        }
      }
    ]
  }
}
```

### 6.8 保存生成配置

```http
POST /api/tasks/{task_id}/generation-config
```

用途：保存音色、成片素材、数字人、输出比例和字幕样式配置。

前端调用时机：用户在配置页点击保存或进入生成进度页前调用。

配置页支持两组二选一：

- 音色：`uploaded_voice` 上传自己的音色样本并填写样本文本，优先走 zero-shot 克隆；或 `preset_voice` 使用默认音色。
- 成片素材：`uploaded_video` 上传自己拍的视频，或 `preset_avatar` 使用默认数字人。

当 `generation_voice_mode=uploaded_voice` 或 `generation_video_mode=uploaded_video` 时，必须传入对应文件信息，并要求 `authorization_confirmed=true`。上传音色还必须传入 `custom_voice_prompt_text`，内容需与音色样本音频一致。

请求示例：

```json
{
  "voice_profile_id": "voice_default",
  "avatar_profile_id": "avatar_default",
  "generation_voice_mode": "uploaded_voice",
  "custom_voice_file_name": "voice_sample.wav",
  "custom_voice_prompt_text": "大家好，我是 Jaden，今天分享一个项目进展。",
  "generation_video_mode": "uploaded_video",
  "custom_video_file_name": "self_video.mp4",
  "authorization_confirmed": true,
  "aspect_ratio": "9:16",
  "subtitle_style": {
    "enabled": true,
    "font_size": 20,
    "position": "bottom",
    "color": "#FFFFFF",
    "stroke": true,
    "font_family": "SimHei"
  },
  "generation_quality": "fast",
  "tuilionnx_sync_offset": 0,
  "avatar_engine": "heygem"
}
```

响应示例：

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "task_01HZX...",
      "generation_voice_mode": "uploaded_voice",
      "custom_voice_path": "storage/tasks/task_01HZX/input/voice_sample.wav",
      "generation_video_mode": "uploaded_video",
      "custom_video_path": "storage/tasks/task_01HZX/input/self_video.mp4",
      "voice_profile_id": "voice_default",
      "avatar_profile_id": "avatar_default",
      "aspect_ratio": "9:16",
      "status": "script_confirmed"
    }
  }
}
```

常见错误：

- `VALIDATION_ERROR`：音色 ID、数字人 ID、字幕样式、自定义音色文件、自自拍视频文件或授权确认不合法。
- 成片合成时 FFmpeg `subtitles` 滤镜会按 `aspect_ratio` 设置 `original_size`（如 1080x1920）与 `MarginV`，确保 `font_size=20`、`position=bottom` 在成片中真实贴底且字号准确。
- `409`：任务尚未确认文案。

### 6.9 开始生成任务

```http
POST /api/tasks/{task_id}/generate
```

用途：开始配音、数字人生成、字幕和成片合成。接口只投递异步任务，不等待生成完成。

前端调用时机：用户点击“开始生成”后调用。

请求示例：

```json
{
  "force": false
}
```

响应示例：

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "task_01HZX...",
      "status": "dubbing",
      "updated_at": "2026-06-01T06:42:00Z"
    }
  }
}
```

常见错误：

- `409`：任务未确认文案、未保存生成配置，或任务已经在生成中。
- `VALIDATION_ERROR`：缺少必要配置。

### 6.10 查询任务状态

```http
GET /api/tasks/{task_id}
```

用途：查询任务状态、失败原因和生成配置摘要。

前端调用时机：进度页轮询调用；任务详情页加载时调用。

响应示例：

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "task_01HZX...",
      "script_source": "video_asr",
      "status": "avatar_generating",
      "duration": 62.5,
      "aspect_ratio": "9:16",
      "error_code": null,
      "error_message": null,
      "created_at": "2026-06-01T06:30:00Z",
      "updated_at": "2026-06-01T06:45:00Z"
    },
    "progress": {
      "stage": "avatar_generating",
      "percent": 65,
      "message": "正在生成数字人口播视频"
    }
  }
}
```

前端轮询建议：

- 任务未完成时每 2-5 秒轮询一次。
- 状态为 `completed` 后停止轮询并请求产物列表。
- 状态为 `failed` 后停止轮询并展示 `error_message` 和重试入口。

### 6.11 从失败节点重试

```http
POST /api/tasks/{task_id}/retry
```

用途：任务失败后，从最近可恢复节点继续执行。

前端调用时机：进度页或失败页中，用户点击“重试”后调用。

**2026-06 行为约束：**

- `error_code=TRANSCRIBE_FAILED` 时返回 409，应走 `POST /api/tasks/{task_id}/retranscribe`。
- 仅 `failed`（非 `retrying`）可进入重试；重复提交返回 409。
- 重试前复验 `_ensure_ready_for_generation`，并清理旧 `tts_audio/avatar_video/subtitle/final_video` 产物记录。
- 生成中（`dubbing`…`composing`）禁止 `save_segments` / `check-script-risk` / `retranscribe`。
- `POST /api/tasks/{task_id}/pre-publish-check` 要求 `status=completed` 且存在 `final_video` 产物。

请求示例：

```json
{
  "from_stage": "avatar_generating"
}
```

响应示例：

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "task_01HZX...",
      "status": "retrying",
      "updated_at": "2026-06-01T06:48:00Z"
    }
  }
}
```

常见错误：

- `409`：任务不是失败状态，或当前失败无法自动重试。

### 6.12 获取任务产物列表

```http
GET /api/tasks/{task_id}/artifacts
```

用途：获取任务相关产物，供前端预览、下载和排障使用。

前端调用时机：任务完成后结果页加载时调用；开发期也可用于展示中间产物。

响应示例：

```json
{
  "success": true,
  "data": {
    "artifacts": [
      {
        "id": "artifact_final_video",
        "task_id": "task_01HZX...",
        "type": "final_video",
        "meta": {
          "duration": 62.5,
          "format": "mp4",
          "size_bytes": 10485760
        },
        "created_at": "2026-06-01T06:50:00Z"
      }
    ]
  }
}
```

安全注意：

- 默认不向前端返回完整本地路径。
- 如需下载，通过 `artifact_id` 调用下载接口。

### 6.13 下载产物

```http
GET /api/artifacts/{artifact_id}/download
```

用途：下载最终视频、字幕或开发期允许下载的中间产物。

前端调用时机：结果页中，用户点击下载按钮后调用。

响应方式：

- 本地存储：后端返回文件流。
- 对象存储：后端返回 `302` 跳转或 JSON 包含短期有效 `download_url`。

JSON 响应示例：

```json
{
  "success": true,
  "data": {
    "download_url": "https://storage.example.com/signed-url",
    "expires_in": 300
  }
}
```

常见错误：

- `404`：产物不存在或文件已被清理。
- `403`：后续接入用户系统后，当前用户无权下载。

### 6.14 查询任务风险审核结果

```http
GET /api/tasks/{task_id}/risk-checks
```

用途：获取任务在输入、文案、生成和发布前各阶段的风险审核结果。

前端调用时机：文案确认页、配置页、结果页和发布前合规检查页加载时调用。

查询参数：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `stage` | 否 | 只查询某一阶段，例如 `script` / `pre_publish`。 |

响应示例：

```json
{
  "success": true,
  "data": {
    "risk_checks": [
      {
        "id": "risk_01HZX...",
        "task_id": "task_01HZX...",
        "stage": "script",
        "risk_status": "warning",
        "risk_level": "medium",
        "risk_types": ["sensitive_keyword"],
        "findings": [
          {
            "id": "finding_01HZX...",
            "type": "sensitive_keyword",
            "target": "script",
            "text": "命中的关键词或说明",
            "position": "第 3 段 / 00:12",
            "suggestion": "建议替换或删除该表述"
          }
        ],
        "reviewed_by": "system",
        "reviewed_at": null,
        "created_at": "2026-06-01T06:40:00Z"
      }
    ]
  }
}
```

### 6.15 人工确认风险结果

```http
POST /api/tasks/{task_id}/risk-checks/{risk_check_id}/confirm
```

用途：用户阅读风险提示后，确认继续生成或继续发布。只允许确认 `warning` 或 `manual_review` 状态的风险结果。

请求示例：

```json
{
  "confirmed": true,
  "confirmation_note": "已确认该内容为自有素材并接受发布风险"
}
```

响应示例：

```json
{
  "success": true,
  "data": {
    "risk_check": {
      "id": "risk_01HZX...",
      "risk_status": "passed",
      "reviewed_by": "user",
      "reviewed_at": "2026-06-01T06:42:00Z"
    },
    "task": {
      "id": "task_01HZX...",
      "status": "script_confirmed"
    }
  }
}
```

常见错误：

- `409`：风险结果为 `blocked`，不能人工确认放行。
- `400`：缺少确认说明或确认值不是 `true`。

### 6.16 执行发布前合规检查

```http
POST /api/tasks/{task_id}/pre-publish-check
```

用途：在下载或发布前，对最终字幕、标题、简介、标签、封面和平台规则做最后一次检查。

请求示例：

```json
{
  "platform": "douyin",
  "title": "视频标题",
  "description": "视频简介",
  "tags": ["AI数字人", "口播"],
  "ai_label_confirmed": true,
  "cover_artifact_id": "artifact_cover"
}
```

响应示例：

```json
{
  "success": true,
  "data": {
    "risk_check": {
      "id": "risk_pre_publish_01HZX...",
      "stage": "pre_publish",
      "risk_status": "manual_review",
      "risk_level": "medium",
      "risk_types": ["platform_rule"],
      "findings": [
        {
          "type": "platform_rule",
          "target": "title",
          "text": "可能需要添加 AI 生成标识",
          "position": "标题",
          "suggestion": "建议在标题、简介或视频画面中标注 AI 生成内容"
        }
      ]
    }
  }
}
```

常见错误：

- `409`：任务尚未完成，不能进行发布前检查。
- `CONTENT_BLOCKED`：发布前检查发现禁止发布内容。

## 7. 状态与前端展示文案

| 状态 | 前端展示文案 | 前端建议行为 |
| --- | --- | --- |
| `uploaded` | 视频已上传，等待识别 | 进入进度页并轮询。 |
| `audio_extracted` | 音频提取完成 | 继续轮询。 |
| `transcribing` | 正在识别文案 | 继续轮询。 |
| `transcribed` | 文案识别完成，请确认 | 跳转或提示进入文案确认页。 |
| `script_pasted` | 文案已提交，等待解析 | 进入进度页并轮询。 |
| `script_parsing` | 正在解析文案 | 继续轮询。 |
| `script_parsed` | 文案解析完成，请确认 | 跳转或提示进入文案确认页。 |
| `script_confirmed` | 文案已确认 | 允许进入配置页。 |
| `content_checking` | 正在检查内容风险 | 继续轮询，必要时展示审核说明。 |
| `content_review_required` | 内容需要人工确认 | 跳转风险提示页，要求用户确认后继续。 |
| `content_rejected` | 内容风险较高，请修改 | 阻止继续生成，引导返回文案或素材修改。 |
| `dubbing` | 正在生成配音 | 继续轮询。 |
| `dubbed` | 配音生成完成 | 继续轮询。 |
| `avatar_generating` | 正在生成数字人口播视频 | 继续轮询。 |
| `avatar_generated` | 数字人视频生成完成 | 继续轮询。 |
| `subtitle_generating` | 正在生成字幕 | 继续轮询。 |
| `composing` | 正在合成最终视频 | 继续轮询。 |
| `publish_checking` | 正在进行发布前合规检查 | 继续轮询或展示检查进度。 |
| `publish_blocked` | 发布前检查未通过 | 禁止直接发布，可允许下载或返回修改。 |
| `publish_ready` | 已通过发布前检查 | 允许进入发布或下载操作。 |
| `completed` | 成片已生成 | 停止轮询，展示结果页。 |
| `failed` | 生成失败 | 展示失败原因和重试入口。 |
| `retrying` | 正在重试 | 继续轮询。 |

## 8. 错误码说明

| 错误码 | 前端展示建议 | 处理方式 |
| --- | --- | --- |
| `VALIDATION_ERROR` | 输入内容不符合要求，请检查后重试。 | 引导用户修改输入，不自动重试。 |
| `ASR_FAILED` | 文案识别失败，请稍后重试。 | 允许用户重试。 |
| `SCRIPT_PARSE_FAILED` | 字幕 / 文案解析失败，请调整格式。 | 引导用户修改文本。 |
| `TTS_FAILED` | 配音生成失败，请稍后重试。 | 允许用户重试。 |
| `AVATAR_FAILED` | 数字人视频生成失败，请稍后重试。 | 允许用户重试。 |
| `COMPOSE_FAILED` | 视频合成失败，请稍后重试。 | 可重试，但后端需记录 FFmpeg 错误。 |
| `RISK_CHECK_FAILED` | 内容风险检查失败，请稍后重试。 | 如为审核服务异常可重试。 |
| `CONTENT_BLOCKED` | 内容存在高风险，请修改后再继续。 | 不自动重试，引导用户修改内容。 |
| `DISTRIBUTE_FAILED` | 平台分发失败，请稍后重试。 | 仅分发能力接入后使用。 |

## 9. 前端联调注意事项

- 创建任务后不要等待生成完成，应立刻进入进度页并通过 `GET /api/tasks/{task_id}` 轮询状态。
- 文案确认前必须允许用户查看和编辑文案，默认使用 `full_script` 完整文案模式，用户可切换为 `timed_segments` 分段时间轴模式。
- `PUT /segments` 适合保存草稿，并应同时保存 `script_generation_mode`；`POST /confirm-script` 才代表用户确认最终文案。
- 任务进入 `dubbing` 之后，前端不应再允许编辑文案；如需修改，应创建新任务或后续设计回退机制。
- 创建任务页的参考视频 / 文案输入不强制统一授权确认；配置页上传自定义音色或自拍视频时，必须要求用户确认素材授权，并将授权记录写入 `authorization_records`。
- 配置页缺少自定义音色、自自拍视频或授权确认时，应在用户点击保存 / 开始生成后提示缺失项，不要在页面初始加载时直接展示红色错误。
- 文案确认后应查询或触发风险审核；`warning` / `manual_review` 必须展示命中位置和处理建议，不能只显示“有风险”。
- 发布前合规检查不应影响用户下载本地视频，但 `blocked` 平台不能自动发布。
- 下载和预览不要直接拼接文件路径，应始终通过后端接口获取。
- 失败重试只对 `failed` 状态开放，且后端根据已有产物决定从哪个节点恢复。

## 10. 后端实现注意事项

- 所有来自用户的文件名都不能直接作为存储路径，必须由后端生成安全文件名。
- FFmpeg 参数必须由后端白名单拼装，不能把用户输入直接传入命令。
- API 层不要直接执行长耗时模型任务，只投递队列并更新状态。
- 每个异步阶段至少记录 `task_id`、阶段、开始时间、结束时间、输入文件、输出文件和错误码。
- 日志可以包含开发排查信息，但接口响应和用户可见日志不能暴露 token、内部命令细节或敏感路径。

## 11. KrLongAI 对齐新增接口（2026-06-18）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tasks/{id}/source-video` | 文案页参考视频预览（本地转存后） |
| POST | `/api/tasks/{id}/retranscribe` | 重新下载/识别参考视频文案（仅 video_asr 任务） |
| GET | `/api/system/runtime-info` | 运行模式、ASR/DeepSeek、合规模式（ai/rules）、模型包装服务 8002/8003/8004 健康 |
| POST | `/api/pipelines/one-click` | 一键追爆款（异步，桌面模式 BackgroundTasks） |
| GET | `/api/tasks/{id}/pipeline-status` | 一键流水线子进度 |
| GET | `/api/tasks` | 任务列表 |
| POST | `/api/tasks/batch` | 批量对标链接任务（Form: source_urls 换行分隔） |
| POST | `/api/tasks/{id}/rewrite-script` | DeepSeek 文案仿写（Key 由服务端 `.env` 配置） |
| POST | `/api/tasks/{id}/generate-publish-metadata` | AI 标题/描述/标签 |
| GET | `/api/tasks/{id}/covers/candidates` | 封面候选帧 |
| POST | `/api/tasks/{id}/covers/generate` | 生成封面 |
| POST | `/api/tasks/{id}/covers/upload` | 上传封面 |
| POST | `/api/tasks/{id}/distributions/batch` | 多平台批量发布 |
| POST | `/api/pipelines/one-click` | 已下线（410），请走分步创作 |
| GET | `/api/tasks/{id}/pipeline-status` | 已下线（410） |

新增任务字段：`source_url`、`pipeline_mode`、`pipeline_stage`（含 `stage_timings`）、`voice_speed`、`background_music_mode`、`ai_watermark_enabled`、`export_without_subtitle`、`avatar_engine`、`generation_quality`、`tuilionnx_sync_offset`。
