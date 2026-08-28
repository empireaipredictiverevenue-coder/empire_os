"""
Empire OS v3 — Shared headless browser tool (Playwright)
=========================================================
Used by crawlers/scrapers to bypass JS-rendered blocks (Yelp,
YellowPages, carrier DRP rosters, Craigslist shells).

No API keys. Uses locally-installed chromium (playwright install chromium).
"""
from __future__ import annotations
import time
from typing import Optional

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


class BrowserTool:
    """Thin wrapper around Playwright chromium. Singleton-ish per process."""

    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self._pw = None
        self._browser = None

    def _ensure(self):
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-setuid-sandbox",
                      "--disable-dev-shm-usage"],
            )

    def new_page(self):
        self._ensure()
        ctx = self._browser.new_context(user_agent=UA,
                                        viewport={"width": 1366, "height": 900},
                                        locale="en-US")
        return ctx.new_page()

    def get_html(self, url: str, wait: str = "domcontentloaded",
                 extra_sleep: float = 2.0) -> Optional[str]:
        """Return rendered HTML for a URL (JS executed)."""
        page = self.new_page()
        try:
            page.goto(url, wait_until=wait, timeout=self.timeout)
            if extra_sleep:
                time.sleep(extra_sleep)
            return page.content()
        except Exception as e:
            return f"<error>{e}</error>"
        finally:
            page.close()

    def get_page(self, url: str, wait: str = "domcontentloaded"):
        """Return the live page object for custom extraction."""
        page = self.new_page()
        page.goto(url, wait_until=wait, timeout=self.timeout)
        return page

    def close(self):
        if self._browser:
            try: self._browser.close()
            except Exception: pass
        if self._pw:
            try: self._pw.stop()
            except Exception: pass
        self._browser = None
        self._pw = None

_TOOL: Optional[BrowserTool] = None
_tls: Optional["threading.local"] = None


def get_tool() -> BrowserTool:
    """Per-thread BrowserTool.

    Playwright sync API binds its greenlet to the creating thread. A global
    singleton breaks when called from anyio.to_thread workers (thread exits,
    greenlet switch fails: 'cannot switch to a different thread'). Thread-local
    instances keep every Playwright object on its owning thread.
    """
    global _tls
    if _tls is None:
        import threading
        _tls = threading.local()
    tool = getattr(_tls, "tool", None)
    if tool is None:
        tool = BrowserTool()
        _tls.tool = tool
    return tool
