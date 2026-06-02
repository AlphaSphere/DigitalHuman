"""外部模型与媒体工具适配层（Adapter Pattern）。

## 设计目的

本包将业务层与各类外部能力解耦：Worker / Service 只调用统一的 Python 类与方法，
不关心底层是 HTTP 微服务、本地 CLI 还是开发用的 Stub 占位实现。

## 三种接入方式

| 方式 | 适用场景 | 代表适配器 |
|------|----------|------------|
| **HTTP** | 独立部署的 AI 推理服务（GPU 容器、FastAPI 等），便于水平扩展与版本隔离 | CozyVoice、HeyGem、Whisper（可选） |
| **CLI** | 成熟命令行工具或第三方 Python 包，本地/Worker 镜像直接调用即可 | FFmpeg、Whisper（本地模式）、social-auto-upload |
| **Stub** | 本地开发、CI、无 GPU 环境；`USE_STUB_MODEL_ADAPTERS=true` 时写入占位文件，跳过重计算 | CozyVoice、HeyGem、FFmpeg、Whisper |

## 各外部服务职责

- **CosyVoice（CozyVoiceAdapter）**：文本转语音（TTS），根据音色配置生成配音 wav。
- **HeyGem（HeyGemAdapter）**：数字人口型驱动，将 TTS 音频与数字人形象合成为口播视频。
- **Whisper（WhisperAdapter）**：语音识别（ASR），从音频/视频提取带时间戳的文案分段。
- **FFmpeg（FFmpegAdapter）**：音视频处理——抽轨、烧录字幕、混音、输出最终 mp4。
- **social-auto-upload（DistributorAdapter）**：多平台视频自动上传（B 站等），通过 sau CLI 完成。
"""
