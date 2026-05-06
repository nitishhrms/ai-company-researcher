import sys
import asyncio
import atexit
from playwright.sync_api import sync_playwright, Browser, Page

# Playwright needs ProactorEventLoop on Windows to start its Node.js driver
# from inside thread pool workers (which is how FastAPI runs sync code).
# SelectorEventLoop (Windows default) does not support create_subprocess_exec.
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

_playwright = None
_browser: Browser = None
_page: Page = None


def get_page() -> Page:
    global _playwright, _browser, _page
    if _page is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
        _page = _browser.new_page()
        _page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    return _page


def _close():
    global _playwright, _browser, _page
    # Do not call browser.close() or playwright.stop() here.
    # Sending close messages to the Playwright Node.js driver during Python
    # exit causes EPIPE because the pipe is already being torn down.
    # The OS kills the Playwright subprocess automatically when Python exits.
    _page = None
    _browser = None
    _playwright = None


atexit.register(_close)
