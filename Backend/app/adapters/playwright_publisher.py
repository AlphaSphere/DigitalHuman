"""Playwright 浏览器自动化发布（抖音/小红书/视频号）。"""

from pathlib import Path

from app.core.config import get_settings


class PlaywrightPublisher:
    """通过 Chrome CDP 连接执行平台发布。"""

    PLAYWRIGHT_PLATFORMS = {"douyin", "xiaohongshu", "wechat_channels"}

    def __init__(self) -> None:
        self.settings = get_settings()

    def upload_video(
        self,
        platform: str,
        file_path: str,
        title: str,
        description: str,
        tags: list[str],
        cover_path: str | None = None,
        attach_cover: bool = False,
    ) -> dict:
        """尝试通过 Playwright 发布视频。"""
        if not self.settings.enable_distribution:
            return {
                "status": "failed",
                "error_message": "分发功能未启用，请设置 ENABLE_DISTRIBUTION=true",
            }
        if self.settings.use_stub_model_adapters:
            return {
                "status": "success",
                "external_url": f"https://example.com/{platform}/stub",
                "raw": {"stub": True, "platform": platform, "cover": cover_path if attach_cover else None},
            }
        if not Path(file_path).exists():
            return {"status": "failed", "error_message": f"视频文件不存在: {file_path}"}

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {
                "status": "failed",
                "error_message": "Playwright 未安装，请在 worker 镜像中安装 playwright",
            }

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(self.settings.playwright_chrome_cdp_url)
                context = browser.contexts[0] if browser.contexts else browser.new_context()
                page = context.new_page()
                upload_url = self._platform_upload_url(platform)
                page.goto(upload_url, timeout=int(self.settings.playwright_publish_timeout_seconds * 1000))
                page.wait_for_timeout(1500)

                uploaded = self._upload_video_file(page, platform, file_path)
                if not uploaded:
                    return {
                        "status": "failed",
                        "error_message": (
                            f"未能自动选择 {platform} 上传控件，请确认 Chrome 已登录创作者中心。"
                            " 可在 docs/technical-architecture.md 查看 Playwright 发布配置说明。"
                        ),
                        "raw": {"upload_url": upload_url},
                    }

                self._fill_publish_form(page, platform, title, description, tags)
                if attach_cover and cover_path and Path(cover_path).exists():
                    self._attach_cover(page, platform, cover_path)

                # 平台 DOM 常变：默认只完成上传与表单填充，由用户确认发布
                return {
                    "status": "success",
                    "external_url": upload_url,
                    "error_message": None,
                    "raw": {
                        "upload_url": upload_url,
                        "platform": platform,
                        "title": title,
                        "tags": tags,
                        "cover_path": cover_path if attach_cover else None,
                        "manual_confirm_required": True,
                    },
                }
        except Exception as exc:
            return {
                "status": "failed",
                "error_message": f"Playwright 发布失败: {exc}。请确保 Chrome 已启动 --remote-debugging-port=9222",
            }

    def _upload_video_file(self, page, platform: str, file_path: str) -> bool:
        """尝试通过 file input 或拖拽区域上传视频。"""
        selectors = {
            "douyin": ['input[type="file"]', 'input[accept*="video"]'],
            "xiaohongshu": ['input[type="file"]', 'input[accept*="video"]'],
            "wechat_channels": ['input[type="file"]', 'input[accept*="video"]'],
        }
        for selector in selectors.get(platform, ['input[type="file"]']):
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue
            try:
                locator.set_input_files(file_path, timeout=8000)
                page.wait_for_timeout(2000)
                return True
            except Exception:
                continue
        return False

    def _fill_publish_form(self, page, platform: str, title: str, description: str, tags: list[str]) -> None:
        """尽力填充标题、简介与标签（平台选择器需随 DOM 变更维护）。"""
        title_selectors = [
            'textarea[placeholder*="标题"]',
            'input[placeholder*="标题"]',
            '[contenteditable="true"]',
        ]
        for selector in title_selectors:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue
            try:
                locator.fill(title[:80])
                break
            except Exception:
                continue

        desc_selectors = ['textarea[placeholder*="简介"]', 'textarea[placeholder*="描述"]']
        for selector in desc_selectors:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue
            try:
                locator.fill(description[:500])
                break
            except Exception:
                continue

        if tags:
            tag_text = " ".join(f"#{tag.lstrip('#')}" for tag in tags[:5])
            tag_selectors = ['input[placeholder*="标签"]', 'input[placeholder*="话题"]']
            for selector in tag_selectors:
                locator = page.locator(selector).first
                if locator.count() == 0:
                    continue
                try:
                    locator.fill(tag_text)
                    break
                except Exception:
                    continue

    def _attach_cover(self, page, platform: str, cover_path: str) -> None:
        cover_selectors = ['input[accept*="image"]', 'input[type="file"][accept*="jpg"]']
        for selector in cover_selectors:
            locator = page.locator(selector).last
            if locator.count() == 0:
                continue
            try:
                locator.set_input_files(cover_path, timeout=5000)
                return
            except Exception:
                continue

    def _platform_upload_url(self, platform: str) -> str:
        mapping = {
            "douyin": "https://creator.douyin.com/creator-micro/content/upload",
            "xiaohongshu": "https://creator.xiaohongshu.com/publish/publish",
            "wechat_channels": "https://channels.weixin.qq.com/platform/post/create",
        }
        return mapping.get(platform, "about:blank")
