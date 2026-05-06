# Agentic AI Research Agent — Full Build Log

---

## What We Are Building

An **AI agent that researches any company for you before a job interview or application.**

You type a company name. The agent:
1. Searches the web for information about the company
2. Opens their actual website in a real browser
3. Reads their careers page, about page, blog posts
4. Clicks links, scrolls pages, fills search forms — just like a human would
5. Writes a structured research report covering product, tech, funding, team, and open roles

**Why this is interesting for job applications:**
Most people spend 1–2 hours manually researching a company before applying. This agent does it in 60 seconds and produces a consistent, structured report every time.

**Why this is interesting as a project:**
This is exactly what companies like Browser Use and Dex are building — LLM-controlled browsers that can navigate the real web. By building it yourself, you understand the primitives: how the agent decides what to do, how the browser is controlled, how results flow back to the LLM.

**Final output after all 7 hours:**
- A Python backend (FastAPI) with a streaming research agent
- A Next.js frontend where you type a company name and watch the research happen live
- Both deployed publicly (Railway + Vercel) with real URLs
- A GitHub repo with README and a GIF demo
- A 90-second Loom video showing it working live

---

## Hr 1: Tavily Web Search — The Baseline Agent

### What We Built
The simplest possible working agent. One tool (web search), one loop (search → think → search → write report).

**Files created:**
- `main.py` — runs the agent, streams events, prints the report
- `agent/graph.py` — LangGraph with two nodes: `agent` (LLM decides) and `tools` (executes the decision)
- `agent/tools.py` — one tool: Tavily web search
- `agent/prompts.py` — tells the LLM what to research and how to format the report
- `agent/state.py` — holds the message history and company name across steps

### Reasoning
**Why LangGraph?** LangGraph lets you build a loop: LLM calls a tool → tool result goes back to LLM → LLM calls another tool → repeat until done. This is called a ReAct agent (Reason + Act). Without LangGraph you'd have to write this loop manually.

**Why Tavily over Google?** Raw Google returns HTML pages. Tavily returns clean text summaries + URLs via a single API call. No HTML parsing, no rate limits, no CAPTCHA. Perfect for the first version.

**Why start here?** Before adding complexity (browser, tracing, error handling), you need a working baseline. If the agent can't research a company with just search, adding a browser won't fix it.

### Output After This Hour
Run `python main.py "OpenAI"` in the terminal and get:

```
Researching: OpenAI
============================================================
[Step 1] Searching: "OpenAI company product mission"
[Step 2] Got search results
[Step 3] Searching: "OpenAI funding investors valuation"
[Step 4] Got search results
[Step 5] Writing final report...

## OpenAI — Research Brief

### What They Do
...
### Funding & Stage
...
### Why They're Interesting
...
============================================================
```
A structured markdown report printed in the terminal. Nothing else yet.

---

## Hr 2: Playwright Browser Automation

### What We Built
Gave the agent a real browser. Now instead of just reading Tavily summaries, the agent can open actual websites, click links, scroll pages, and fill forms — exactly like a human researcher would.

**Files created/changed:**
- `agent/browser.py` — new file, manages one shared Chrome browser session
- `agent/tools.py` — added 4 new browser tools on top of web search
- `agent/prompts.py` — updated to teach the LLM when and how to use browser tools
- `agent/graph.py` — upgraded LLM from Haiku to Sonnet

### Reasoning
**Why add a browser at all?** Tavily gives summaries, not full pages. The agent misses things: actual job listings, exact team members, real product descriptions. A browser reads what a human reads.

**Why a singleton browser (`browser.py`)?** Playwright takes 1–2 seconds to launch Chrome. If every tool call opened a new browser, a 10-step run wastes 20 seconds and leaves orphaned Chrome processes running. One shared session solves both problems.

**Why these 4 tools specifically?** They cover the complete browser interaction loop:
- `visit_webpage` → navigate to a URL and read it
- `click_element` → follow a link or press a button
- `scroll_page` → reveal lazy-loaded content
- `fill_form_field` → use a site's own search box

This is exactly the primitive set Browser Use exposes to its LLMs.

**Why upgrade to Sonnet?** Haiku is fast and cheap but struggles to correctly sequence 5 different tools across multiple reasoning steps. Sonnet reliably decides: search first → visit homepage → click Careers → scroll → write report. For a demo the cost tradeoff strongly favors reliability.

**Why update the prompt?** The LLM doesn't automatically know when to use new tools. The prompt teaches it the exact workflow: search first, then open URLs, then click into sub-pages. Without this guidance the agent ignores `visit_webpage` entirely.

### Output After This Hour
Same terminal output as Hr 1, but now the steps show browser actions:

```
[Step 1] web_search: "Anthropic AI company"
[Step 2] Tool result received
[Step 3] visit_webpage: 'https://anthropic.com'
[Step 4] Tool result received
[Step 5] click_element: 'Careers'
[Step 6] Tool result received
[Step 7] Writing final report...
```
The report is now richer — actual job titles, real team bios, exact product descriptions — because the agent read the real pages, not just summaries.

---

## Hr 3: LangSmith Tracing

### What We Built
Full observability. Every LLM call and tool call is now logged to LangSmith's dashboard automatically. After each run, the terminal prints a direct link to the trace.

**Files changed:**
- `requirements.txt` — added `langsmith`
- `main.py` — wired in the tracer + prints the trace URL after each run

### Reasoning
**Why LangSmith?** When an agent does something unexpected — skips a tool, writes a bad report, calls the wrong URL — you need to see exactly what happened. LangSmith shows you the full trace: every message, every tool input/output, every token count, every latency. Without it you're debugging blind.

**Why set it up now (Hr 3) and not later?** Every run from Hr 3 onwards gets automatically logged. By the time you deploy in Hr 6, you'll have a history of real traces to show interviewers. Also, debugging Hr 4 error handling is much easier when you can see exactly which step failed and why.

**Why callbacks instead of manual logging?** `config={"callbacks": [tracer]}` hooks into LangGraph's internal event system. You write zero logging code — LangSmith gets notified automatically before and after every node execution. If you logged manually, you'd miss internal details like token counts and model parameters.

**How it works in one line:**
```
LangChainTracer → plugged into graph.stream() → auto-logs everything → LangSmith API → dashboard
```

### Output After This Hour
Same terminal output as Hr 2, plus one new line at the end:

```
LangSmith trace: https://smith.langchain.com/runs/abc123...
```

Click that link and you see a timeline like this in the browser:

```
▼ RunnableSequence  [4.2s total]
  ▼ agent  [1.1s]   — LLM call — 823 tokens in, 412 out
  ▼ tools  [2.8s]
    ▼ visit_webpage  [2.1s]   input: {url: "https://anthropic.com"}
                              output: "Anthropic is an AI safety company..."
    ▼ web_search  [0.7s]      input: {query: "Anthropic funding"}
                              output: "Anthropic raised $7.3B..."
  ▼ agent  [1.3s]   — LLM call — writing final report
```

---

## Hr 4: Error Handling *(coming next)*

### What We Will Build
Make the agent production-grade. Right now if a webpage times out, a tool crashes, or the LLM loops forever, the whole script crashes. Hr 4 fixes all three.

**Planned changes:**
- `tenacity` retry logic — if a tool fails, retry it up to 3 times with exponential backoff before giving up
- Max iterations guard — if the agent loops more than 10 times, stop it and return whatever it has
- Tool timeout handling — if a webpage takes more than 15 seconds, return an error string instead of hanging

### Reasoning
**Why tenacity?** Network calls (web search, page loads) fail randomly — rate limits, DNS failures, slow servers. Retrying once or twice silently fixes 90% of transient errors without the user noticing.

**Why a max iterations guard?** Without one, a confused agent can loop forever calling tools and burning API credits. A hard limit of 10 steps caps the worst case.

**Why now, before the frontend?** Hr 5 adds a streaming frontend. If the backend crashes mid-stream, the frontend gets a broken connection with no error message. Solid error handling in the backend makes the frontend much simpler to build.

### Output After Hr 4
The agent becomes resilient. If a page fails to load, you see:
```
[Step 3] visit_webpage: 'https://example.com' — retrying (1/3)...
[Step 3] visit_webpage: 'https://example.com' — retrying (2/3)...
[Step 3] visit_webpage: 'https://example.com' — failed after 3 attempts, skipping
```
Instead of a crash, the agent continues with the information it already has.

---

## Hr 5: Next.js Frontend with Streaming *(coming)*

### What We Will Build
A web UI. Instead of running `python main.py "Stripe"` in a terminal, you open a browser, type "Stripe" in a text box, click Research, and watch the agent's steps appear on screen in real time as they happen.

**Planned changes:**
- FastAPI backend — wraps the existing Python agent with HTTP endpoints
- Server-Sent Events (SSE) — streams each step from the backend to the browser as it happens (not waiting for the full report)
- Next.js frontend — text input + live step log + final report display

### Reasoning
**Why streaming (SSE) instead of waiting for the full result?** The agent takes 30–60 seconds. A blank loading spinner for 60 seconds feels broken. Streaming each step as it happens (`Searching... → Visiting page... → Clicking Careers...`) makes it feel fast and alive — the user sees progress immediately.

**Why Next.js?** It's the industry standard for React frontends. Vercel (the company behind Next.js) offers free hosting. Deploying a Next.js app to Vercel takes 2 minutes.

**Why FastAPI?** It's Python, so the existing agent code drops in with no rewriting. It also has built-in SSE support (`StreamingResponse`) which pairs perfectly with Next.js.

### Output After Hr 5
A locally running web app at `http://localhost:3000`. You type a company name, click a button, and watch the research unfold live on screen, line by line, ending with the full formatted report.

---

## Hr 6: Deploy to Railway + Vercel *(coming)*

### What We Will Build
Two public URLs that anyone on the internet can use.

**Planned changes:**
- FastAPI backend deployed to Railway (free tier) → `https://research-agent.railway.app`
- Next.js frontend deployed to Vercel (free tier) → `https://research-agent.vercel.app`

### Reasoning
**Why deploy at all?** A project that only runs on your laptop is not a portfolio piece — it's a local script. A live URL is something you can send to a recruiter, paste in a job application, or demo in an interview. It proves the thing actually works.

**Why Railway for the backend?** Railway runs Docker containers on a free tier with no credit card required. FastAPI packages cleanly into a Docker container. The entire deploy is one CLI command.

**Why Vercel for the frontend?** Vercel is purpose-built for Next.js. Deploy is `vercel --prod`. Free tier includes a custom subdomain and automatic HTTPS.

### Output After Hr 6
Two public URLs. Anyone can visit `https://research-agent.vercel.app`, type a company name, and get a live research report. This is what you put in your resume and GitHub README.

---

## Hr 7: Loom Demo + GitHub Polish *(coming)*

### What We Will Build
A shareable, professional GitHub repo that tells the full story of the project.

**Planned changes:**
- Record a 90-second Loom video showing the agent researching a company live
- Create a GIF from the Loom (10 seconds, shows the live streaming UI)
- Write a README with: what it does, architecture diagram, setup instructions, live demo link
- Push everything to GitHub

### Reasoning
**Why a Loom video?** Recruiters don't run code. A 90-second video showing the agent working live does more than any README. It proves the project is real and that you can explain what you built.

**Why a GIF in the README?** GitHub README renders GIFs inline. The first thing a recruiter or engineer sees when they open your repo is the agent working. No clicking required.

**Why bother with a polished README?** A bare repo with no README signals "hobby project." A README with a live demo link, architecture explanation, and setup instructions signals "engineer who ships."

### Output After Hr 7
A complete, public GitHub repo that looks like a real open source project — with a live demo, a video, and a GIF. This is the final deliverable you reference in job applications.
