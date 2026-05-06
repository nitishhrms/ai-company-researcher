from langchain_tavily import TavilySearch
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential
from .browser import get_page


MAX_RETRIES = 2


def _on_retry(retry_state):
    print(f"  Retrying... attempt {retry_state.attempt_number}/{MAX_RETRIES}")


# ── Tool 1: Web search ────────────────────────────────────────────────────────

web_search = TavilySearch(max_results=5, name="web_search")


# ── Retry-wrapped browser helpers (not tools themselves) ──────────────────────

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    before_sleep=_on_retry,
    reraise=True,
)
def _load_page(page, url: str) -> str:
    page.goto(url, wait_until="domcontentloaded", timeout=8000)
    return page.inner_text("body")


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    before_sleep=_on_retry,
    reraise=True,
)
def _click(page, text: str) -> str:
    page.get_by_text(text, exact=False).first.click()
    page.wait_for_load_state("domcontentloaded", timeout=10000)
    return page.url


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    before_sleep=_on_retry,
    reraise=True,
)
def _fill(page, selector: str, value: str) -> str:
    page.fill(selector, value)
    page.keyboard.press("Enter")
    page.wait_for_load_state("domcontentloaded", timeout=10000)
    return page.url


# ── Tool 2: Visit a URL and read its content ──────────────────────────────────
@tool
def visit_webpage(url: str) -> str:
    """Navigate to a URL and return the page's visible text (first 4000 chars)."""
    page = get_page()
    try:
        text = _load_page(page, url)
        return text[:4000].strip()
    except Exception as e:
        return f"Failed to load {url} after {MAX_RETRIES} attempts: {e}"


# ── Tool 3: Click an element by visible text ──────────────────────────────────
@tool
def click_element(text: str) -> str:
    """Click the first visible element on the current page whose text matches.
    Returns the new URL after navigation (if any)."""
    page = get_page()
    try:
        new_url = _click(page, text)
        return f"Clicked '{text}'. Current URL: {new_url}"
    except Exception as e:
        return f"Could not click '{text}' after {MAX_RETRIES} attempts: {e}"


# ── Tool 4: Scroll the current page ──────────────────────────────────────────
@tool
def scroll_page(direction: str) -> str:
    """Scroll the current browser page. direction must be 'down' or 'up'."""
    page = get_page()
    key = "PageDown" if direction.lower() == "down" else "PageUp"
    page.keyboard.press(key)
    return f"Scrolled {direction}. Current URL: {page.url}"


# ── Tool 5: Fill and submit a form field ──────────────────────────────────────
@tool
def fill_form_field(selector: str, value: str) -> str:
    """Fill an input field (identified by CSS selector) with a value, then press Enter.
    Example selector: 'input[name=\"q\"]' for Google search."""
    page = get_page()
    try:
        new_url = _fill(page, selector, value)
        return f"Filled '{selector}' with '{value}'. Current URL: {new_url}"
    except Exception as e:
        return f"Error filling form after {MAX_RETRIES} attempts: {e}"


def get_tools():
    return [web_search, visit_webpage, click_element, scroll_page, fill_form_field]
