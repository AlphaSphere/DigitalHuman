"""DeepSeek LLM 适配器：文案仿写、发布元信息、封面文案。"""

import json
import re
from typing import Any

import httpx

from app.core.config import get_settings


class DeepSeekAdapter:
    """DeepSeek Chat Completions API 适配器。"""

    def __init__(self, api_key: str | None = None) -> None:
        self.settings = get_settings()
        self.api_key = (api_key or self.settings.deepseek_api_key or "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_key) and self.settings.enable_llm_rewrite

    def rewrite_script(
        self,
        script: str,
        mode: str = "auto",
        instruction: str | None = None,
        style: str | None = None,
        segment_count: int = 1,
    ) -> str:
        """仿写口播文案，返回改写后的全文。"""
        if not self.is_configured():
            raise RuntimeError("未配置 DeepSeek API Key，请在文案页填写或在 .env 设置 DEEPSEEK_API_KEY")

        style_hint = {
            "viral_spoken": "爆款口播风格，开头有钩子、节奏紧凑、适合短视频",
            "formal": "正式专业风格，表达清晰可信",
            "humorous": "幽默轻松风格，口语化但不失重点",
            "custom": "保持自然口播风格",
        }.get(style or "viral_spoken", "爆款口播风格")

        segment_hint = ""
        if segment_count > 1:
            segment_hint = f"请改写为 {segment_count} 个段落，段落之间用空行分隔，每段对应原视频一个时间片段。"

        if mode == "instruction" and instruction:
            user_prompt = (
                f"请按以下要求改写口播文案：{instruction}\n"
                f"{segment_hint}\n\n原文：\n{script}"
            )
        else:
            user_prompt = (
                f"请将以下口播文案改写为{style_hint}，保持核心信息与事实不变，适合数字人口播。"
                f"{segment_hint}\n\n原文：\n{script}"
            )

        raw = self._chat(
            "你是短视频口播文案专家。只输出改写后的文案正文，不要标题、解释或 markdown。",
            user_prompt,
        )
        return _strip_code_fence(raw)

    def generate_publish_metadata(
        self,
        script: str,
        platform: str | None = None,
        tone: str = "viral",
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """生成标题、描述与话题标签。"""
        adapter = DeepSeekAdapter(api_key=api_key)
        if not adapter.is_configured():
            return {
                "title": "AI 数字人口播视频",
                "description": script[:100],
                "tags": ["AI数字人", "口播", "内容创作"],
            }
        platform_name = platform or "douyin"
        prompt = (
            f"根据以下口播文案，为{platform_name}平台生成发布信息。"
            f"以 JSON 返回：title(<=30字), description(<=200字), tags(3-5个字符串数组)。"
            f"语气：{tone}。\n\n文案：\n{script}"
        )
        raw = adapter._chat("只输出合法 JSON，不要 markdown。", prompt)
        try:
            payload = json.loads(_strip_code_fence(raw).replace("json", "", 1))
            return {
                "title": str(payload.get("title", "AI 数字人口播视频"))[:100],
                "description": str(payload.get("description", ""))[:500],
                "tags": [str(tag) for tag in payload.get("tags", [])][:10],
            }
        except json.JSONDecodeError:
            return {
                "title": "AI 数字人口播视频",
                "description": script[:200],
                "tags": ["AI数字人", "口播"],
            }

    def check_script_compliance(self, script: str) -> dict[str, Any]:
        """DeepSeek 合规审查：返回 overall_status 与结构化 findings。"""
        if not self.is_configured():
            raise RuntimeError("未配置 DeepSeek API Key，请在 .env 设置 DEEPSEEK_API_KEY")

        prompt = (
            "请审查以下短视频口播文案的内容合规风险，关注：广告法极限词、收益承诺、隐私信息、"
            "版权/肖像/声音授权、平台 AI 标识要求等。\n\n"
            "只输出合法 JSON，不要 markdown。格式：\n"
            '{"overall_status":"passed|warning|manual_review|blocked",'
            '"findings":[{"type":"sensitive_keyword|privacy|platform_rule|copyright|portrait|voice",'
            '"text":"命中的词句","quote":"原文片段","start":0,"end":2,"line":1,"suggestion":"修改建议"}]}\n\n'
            "规则：\n"
            "- passed：无明显风险，findings 可为空\n"
            "- warning：轻微提示\n"
            "- manual_review：需人工确认（如 AI 标识、授权边界）\n"
            "- blocked：隐私泄露、违法、严重违规\n"
            "- start/end 为原文中的字符下标（从 0 起），line 为行号（从 1 起）\n"
            "- text 必须是原文中真实存在的连续子串\n"
            "- 若问题不在正文（如发布时需标注 AI 生成），设置 in_script: false，且不要填写 start/end\n\n"
            f"文案：\n{script}"
        )
        raw = self._chat(
            "你是短视频内容合规审核专家，输出严格 JSON。",
            prompt,
            temperature=0.2,
        )
        try:
            payload = json.loads(_strip_code_fence(raw))
        except json.JSONDecodeError as exc:
            raise RuntimeError("DeepSeek 合规检查返回格式无效，请重试") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("DeepSeek 合规检查返回格式无效，请重试")
        return payload

    def generate_cover_copy(self, script: str, highlight_words: list[str] | None = None) -> dict[str, Any]:
        """生成封面文案与高亮词。"""
        if not self.is_configured():
            return {"cover_text": script[:20], "highlight_words": highlight_words or ["爆款"]}
        prompt = (
            "根据口播文案生成短视频封面文案，JSON 格式："
            "cover_text(<=16字), highlight_words(1-3个词的数组)。\n\n"
            f"文案：\n{script}"
        )
        raw = self._chat("只输出 JSON。", prompt)
        try:
            payload = json.loads(_strip_code_fence(raw).replace("json", "", 1))
            return {
                "cover_text": str(payload.get("cover_text", script[:16]))[:32],
                "highlight_words": [str(w) for w in payload.get("highlight_words", [])][:5],
            }
        except json.JSONDecodeError:
            return {"cover_text": script[:16], "highlight_words": ["爆款"]}

    def _chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        if not self.api_key:
            raise RuntimeError("未配置 DEEPSEEK_API_KEY")
        url = f"{self.settings.deepseek_base_url.rstrip('/')}/v1/chat/completions"
        try:
            with httpx.Client(timeout=self.settings.deepseek_timeout_seconds) as client:
                response = client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.settings.deepseek_model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "temperature": temperature,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:200] if exc.response else str(exc)
            raise RuntimeError(f"DeepSeek 调用失败 ({exc.response.status_code})：{detail}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"无法连接 DeepSeek 服务：{exc}") from exc


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()
