# Errors Encountered — Agentic AI Research Agent

---

## Error 1: `ModuleNotFoundError: No module named 'langchain.callbacks'`

### Where it appeared
`main.py` on import

### Full error
```
from langchain.callbacks.tracers import LangChainTracer
ModuleNotFoundError: No module named 'langchain.callbacks'
```

### Why it happened
We imported `LangChainTracer` from `langchain.callbacks.tracers` which was the old import path. In newer versions of LangChain (0.2+), the codebase was restructured and `LangChainTracer` moved to `langchain_core`. The base `langchain` package was also not installed — only `langchain-anthropic` and `langchain-core` were in requirements.txt.

### Fix
Changed the import in both `main.py` and `api.py`:
```python
# Before (wrong — old path)
from langchain.callbacks.tracers import LangChainTracer

# After (correct — new path)
from langchain_core.tracers.langchain import LangChainTracer
```
Also added `langchain>=0.2.0` to `requirements.txt`.

---

## Error 2: Empty Report (no output between `====` lines)

### Where it appeared
`main.py` — after running `python main.py "OpenAI"`

### Full error
```
============================================================

============================================================
LangSmith trace: https://smith.langchain.com/runs/...
```
No steps printed. No report content.

### Why it happened
The model ID `claude-sonnet-4-5` was outdated/incorrect. When LangChain sent the request to the Anthropic API with a wrong model ID, the model returned an empty response — no tool calls, no content. The agent loop ran but produced nothing because `msg.content` was an empty string.

### Fix
Updated the model ID in `agent/graph.py`:
```python
# Before
llm = ChatAnthropic(model="claude-sonnet-4-5", temperature=0).bind_tools(tools)

# After
llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0).bind_tools(tools)
```

---

## Error 3: `greenlet.error: cannot switch to a different thread`

### Where it appeared
On Python script exit — in the `atexit` callback in `browser.py`

### Full error
```
Exception ignored in atexit callback: <function _close at 0x...>
greenlet.error: cannot switch to a different thread (which happens to have exited)
```

### Why it happened
Playwright's sync API uses **greenlets** — a mini-threading system — to bridge async Playwright code into synchronous Python. The greenlet that owns the browser session was created in the main thread. When the script exits, Python's `atexit` tries to run `_close()` which calls `_browser.close()`. This sends a message to the Playwright Node.js driver — but it requires switching to the Playwright greenlet. By the time `atexit` runs, the greenlet's thread context has already exited. You cannot switch greenlets across threads, so it crashes.

### Fix
Removed the explicit `_browser.close()` and `_playwright.stop()` calls from `_close()`. The OS automatically kills the Playwright Node.js subprocess when Python exits — no manual cleanup needed.
```python
def _close():
    global _playwright, _browser, _page
    # Do NOT call _browser.close() or _playwright.stop() here
    # — causes greenlet thread-switch error on exit.
    _page = None
    _browser = None
    _playwright = None
```

---

## Error 4: `EPIPE: broken pipe` (Node.js crash on exit)

### Where it appeared
After the report printed — on script exit, in the Playwright Node.js driver

### Full error
```
Error: EPIPE: broken pipe, write
    at Socket._write (node:internal/net:75:18)
    at PipeTransport.send (playwright/driver/.../pipeTransport.js:52:21)
errno: -4047, syscall: 'write', code: 'EPIPE'
```

### Why it happened
When Python exits, it closes the pipe (the communication channel) between Python and Playwright's Node.js driver subprocess. The Node.js driver doesn't know Python is exiting — it's still trying to send one last event through the pipe. The pipe is already closed, so the write fails with EPIPE (Broken Pipe). This is a known Windows issue with Playwright's sync API — the Node.js driver has no graceful shutdown path when the pipe is abruptly closed.

### Fix (partial)
Added `os._exit(0)` at the end of `main.py`. This exits Python instantly without running atexit handlers, killing the Node.js subprocess immediately before it has a chance to send the failing message.
```python
if __name__ == "__main__":
    company = sys.argv[1] if len(sys.argv) > 1 else "Dex"
    research_company(company)
    os._exit(0)  # kill Playwright Node.js subprocess instantly, prevents EPIPE
```
**Note:** This error does not appear in the FastAPI server (`api.py`) because the server stays running — there is no abrupt exit between requests.

---

## Error 5: `uvicorn — Could not import module "api"`

### Where it appeared
When starting the FastAPI server

### Full error
```
ERROR: Error loading ASGI app. Could not import module "api".
INFO: Will watch for changes in these directories: ['E:\\personal resume  projects\\agentic ai']
```

### Why it happened
Uvicorn was run from the **parent folder** (`agentic ai`) instead of the project folder (`agentic ai research agent`). The `api.py` file lives inside the project folder. Uvicorn looks for `api.py` in the current working directory — since it was run from the wrong folder, it couldn't find it.

### Fix
Run uvicorn from inside the correct project directory:
```powershell
cd "E:\personal resume  projects\agentic ai\agentic ai research agent"
uvicorn api:app --reload --port 8000
```

---

## Error 6: `NotImplementedError` in `asyncio.create_subprocess_exec`

### Where it appeared
FastAPI endpoint — when `visit_webpage` tool was called for the first time

### Full error
```
File "agent\browser.py", line 12, in get_page
    _playwright = sync_playwright().start()
...
File "D:\python 3.10\lib\asyncio\base_events.py", line 498, in _make_subprocess_transport
    raise NotImplementedError
```

### Why it happened
This is the most technical error. Three layers are involved:

**Layer 1 — FastAPI runs sync code in a thread pool.**
When you call a sync endpoint in FastAPI, it doesn't run in the main thread. It runs in a worker thread managed by `anyio`. This is so the async event loop (main thread) is never blocked.

**Layer 2 — Playwright needs to start a Node.js subprocess.**
`sync_playwright().start()` launches Playwright's Node.js driver as a subprocess. Internally it uses Python's `asyncio.create_subprocess_exec` to do this.

**Layer 3 — Windows event loop limitation.**
On Windows, Python has two event loop types:
- `SelectorEventLoop` — the default. Does NOT support `create_subprocess_exec` from worker threads.
- `ProactorEventLoop` — supports everything including subprocesses from any thread.

When Playwright ran inside FastAPI's thread pool worker, the worker thread created a new event loop. Because the global policy was still `SelectorEventLoop`, the new loop was a `SelectorEventLoop`. When Playwright tried to start the Node.js subprocess, it hit `NotImplementedError` because `SelectorEventLoop` doesn't support subprocess creation from threads.

### Fix
Set the global asyncio event loop policy to `WindowsProactorEventLoopPolicy` at the top of `browser.py`, before any Playwright code runs:
```python
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
```
Now every new event loop — including the ones created inside FastAPI's thread pool workers — uses `ProactorEventLoop`, which supports subprocess creation from any thread.

---

## Error 7: `Max iterations (10) reached — stopping agent`

### Where it appeared
During the Stripe research run in the terminal

### Full output line
```
Max iterations (10) reached — stopping agent.
[Step 19] Writing final report...
```

### Why it happened
`MAX_STEPS = 10` was set in `graph.py`. The `steps` counter in state only increments when the **agent node** runs (not the tools node). The local `step` counter in `main.py` increments for every event (both agent and tools). So while the terminal showed `[Step 18]`, the actual agent node had only run ~9 times — hitting the limit of 10.

The agent stopped tool-calling as expected, but since the LLM was mid-research, it wrote a final report with what it had gathered so far (which was still comprehensive).

### Fix
Increased `MAX_STEPS` from 10 to 15 in `agent/graph.py`:
```python
MAX_STEPS = 15
```

---

---

## Error 8: `Invalid value for '--port': '$PORT' is not a valid integer`

### Where it appeared
Railway deployment — container kept crashing and restarting in a loop

### Full error
```
Usage: uvicorn [OPTIONS] APP
Try 'uvicorn --help' for help.
Error: Invalid value for '--port': '$PORT' is not a valid integer.
```

### Why it happened
The Dockerfile `CMD` was written in shell form:
```dockerfile
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
```
Shell form is supposed to run under `/bin/sh -c`, which expands `$PORT`. However, Railway's container runtime did not expand the variable — it passed the literal string `$PORT` directly to uvicorn, which rejected it as a non-integer.

### Fix
Changed CMD to exec form with an explicit `sh -c` call, which guarantees shell variable expansion regardless of runtime:
```dockerfile
# Before
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}

# After
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

---

## Error 9: `Did not find tavily_api_key` — Server crashes on startup

### Where it appeared
Railway deployment — server crashed immediately on every start, never became healthy

### Full error
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for TavilySearchAPIWrapper
  Value error, Did not find tavily_api_key, please add an environment variable
  `TAVILY_API_KEY` which contains it, or pass `tavily_api_key` as a named parameter.

File "/app/agent/tools.py", line 16, in <module>
    web_search = TavilySearch(max_results=5, name="web_search")
```

### Why it happened
Two problems combined:

**Problem 1 — Missing env var on Railway:** `TAVILY_API_KEY` (and the other keys) were never added to Railway's Variables tab. Railway does not read your local `.env` file — env vars must be added manually in the dashboard.

**Problem 2 — Module-level instantiation:** `TavilySearch` was created at the top of `tools.py` as a module-level variable (line 16), not inside a function. This means it runs the moment uvicorn imports the app — before any request arrives. If the env var is missing, the import itself crashes and the server never starts.

### Fix
**Fix 1 (required):** Added all env vars to Railway dashboard → service → Variables:
```
ANTHROPIC_API_KEY, TAVILY_API_KEY, LANGCHAIN_API_KEY,
LANGCHAIN_TRACING_V2, LANGCHAIN_PROJECT, PYTHONUNBUFFERED
```

**Fix 2 (code):** Moved `TavilySearch` instantiation inside `get_tools()` so it only runs when first request comes in, not at import time:
```python
# Before — crashes server on startup if env var missing
web_search = TavilySearch(max_results=5, name="web_search")

def get_tools():
    return [web_search, ...]

# After — fails gracefully at request time, server still starts
def get_tools():
    web_search = TavilySearch(max_results=5, name="web_search")
    return [web_search, ...]
```

---

## Error 10: CORS blocked — `No 'Access-Control-Allow-Origin' header is present`

### Where it appeared
Browser console — when the Vercel frontend tried to call the Railway backend

### Full error
```
Access to fetch at 'https://ai-company-researcher-production.up.railway.app/research'
from origin 'https://frontend-qwerty15.vercel.app' has been blocked by CORS policy:
Response to preflight request doesn't pass access control check:
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

### Why it happened
The CORS `allow_origins` list in `api.py` contained `"https://*.vercel.app"` — intended to match all Vercel subdomains. But FastAPI's `CORSMiddleware` (from Starlette) does **not** support wildcard subdomains. It compares origins as exact strings only. The literal string `"https://*.vercel.app"` never matched the actual origin `"https://frontend-qwerty15.vercel.app"`, so every preflight OPTIONS request was rejected.

### Fix
Replaced the wildcard with the exact Vercel deployment URL:
```python
# Before — wildcard looks right but doesn't work
allow_origins=[
    "http://localhost:3000",
    "https://*.vercel.app",   # ← treated as a literal string, never matches
]

# After — exact URL
allow_origins=[
    "http://localhost:3000",
    "https://frontend-qwerty15.vercel.app",   # ← exact match, works
]
```

---

---

## Error 11: Railway not auto-deploying from GitHub pushes

### Where it appeared
Every time we pushed a fix to GitHub, Railway kept running the old code. The CORS and env var fixes never took effect despite successful `git push`.

### Why it happened
Railway was deployed manually the first time (either via CLI or dashboard drag-and-drop), which creates a deployment with **no GitHub connection**. Railway does not automatically link to GitHub unless you explicitly connect the repo in the dashboard. Every subsequent `git push` went to GitHub but Railway never saw it — it was still running the original uploaded code.

### Fix
Two steps:
1. Used `railway up --detach` from the CLI to force-upload local code directly to Railway (bypasses GitHub entirely)
2. Connect Railway to GitHub permanently: Railway dashboard → service → Settings → Source → Connect Repo → select `nitishhrms/ai-company-researcher` → from now on every `git push` triggers an auto-redeploy

---

## Error 12: Railway proxy strips `Access-Control-Allow-Origin` — CORS never resolved at the app level

### Where it appeared
Browser console — persisted even after `allow_origins=["*"]` and an explicit `@app.options("/research")` endpoint were deployed

### Full error
```
Access to fetch at 'https://ai-company-researcher-production.up.railway.app/research'
from origin 'https://frontend-qwerty15.vercel.app' has been blocked by CORS policy:
Response to preflight request doesn't pass access control check:
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

### Why it happened
Railway's infrastructure has a reverse proxy (load balancer) that sits in front of every deployed app. When a browser sends an OPTIONS preflight to the Railway URL, Railway's proxy intercepts it and returns its own 400 response — **before the request ever reaches FastAPI**. This proxy strips `Access-Control-Allow-Origin` from the response. No amount of FastAPI CORS configuration fixes this because FastAPI never sees the preflight request.

Confirmed via curl:
```bash
curl -X OPTIONS https://ai-company-researcher-production.up.railway.app/research \
  -H "Origin: https://frontend-qwerty15.vercel.app" \
  -H "Access-Control-Request-Method: POST" -v

# Response:
< HTTP/1.1 400 Bad Request
< Access-Control-Allow-Headers: content-type   ← proxy's own headers
< Access-Control-Allow-Methods: POST, GET, OPTIONS
# Access-Control-Allow-Origin is completely absent
```

### Fix
Bypass CORS entirely using **Vercel rewrites as a server-side proxy**. Instead of the browser calling Railway directly, it calls a Vercel route (`/api/research`) on the same origin (no CORS check). Vercel's edge network forwards the request to Railway server-to-server (no browser involved, no CORS).

**`frontend/next.config.js`:**
```javascript
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/research",
        destination: "https://ai-company-researcher-production.up.railway.app/research",
      },
    ];
  },
};
```

**`frontend/app/page.tsx`** — changed fetch URL:
```typescript
// Before — browser calls Railway directly → CORS blocked
const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/research`, ...)

// After — browser calls Vercel (same origin) → no CORS
const response = await fetch(`/api/research`, ...)
```

**Why this works:** Browser → Vercel (same origin, no CORS) → Railway (server-to-server, no CORS). The proxy pattern completely sidesteps the browser's CORS enforcement.

---

## Summary Table

| # | Error | Root Cause | Fixed In |
|---|---|---|---|
| 1 | `ModuleNotFoundError: langchain.callbacks` | Wrong import path after LangChain restructure | `main.py`, `api.py` |
| 2 | Empty report | Wrong model ID `claude-sonnet-4-5` | `agent/graph.py` |
| 3 | `greenlet.error: cannot switch thread` | Playwright greenlet called from wrong thread in atexit | `agent/browser.py` |
| 4 | `EPIPE: broken pipe` | Node.js driver writes to closed pipe on Python exit | `main.py` (`os._exit`) |
| 5 | `Could not import module "api"` | uvicorn run from wrong directory | Terminal command |
| 6 | `NotImplementedError` in asyncio | Windows SelectorEventLoop can't create subprocesses from threads | `agent/browser.py` |
| 7 | Max iterations reached too early | `MAX_STEPS=10` too low for thorough research | `agent/graph.py` |
| 8 | `'$PORT' is not a valid integer` | Railway didn't expand `$PORT` in shell-form CMD | `Dockerfile` |
| 9 | `Did not find tavily_api_key` — startup crash | Missing Railway env vars + module-level tool instantiation | Railway dashboard + `agent/tools.py` |
| 10 | CORS blocked on preflight | FastAPI CORSMiddleware doesn't support wildcard subdomains | `api.py` |
| 11 | Railway not auto-deploying from GitHub | No GitHub repo connected — Railway ran original upload only | Railway dashboard → Connect Repo |
| 12 | Railway proxy strips `Access-Control-Allow-Origin` | Railway's load balancer intercepts OPTIONS before FastAPI | Vercel rewrites proxy (`next.config.js` + `page.tsx`) |
