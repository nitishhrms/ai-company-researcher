import os
import json
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from langchain_core.tracers.langchain import LangChainTracer
from agent.graph import build_graph

app = FastAPI()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "600",
}


class ResearchRequest(BaseModel):
    company: str


# build once at startup — not on every request
_graph = build_graph()


# Handle preflight for /research — CORSMiddleware removed because it intercepts
# OPTIONS before our route and returns 400 on Railway's proxy
@app.options("/research")
def research_options():
    return Response(status_code=200, headers=CORS_HEADERS)


def stream_research(company: str):
    project = os.getenv("LANGCHAIN_PROJECT", "research-agent")
    tracer = LangChainTracer(project_name=project)
    for event in _graph.stream(
        {
            "messages": [HumanMessage(content=f"Research the startup: {company}")],
            "company": company,
            "steps": 0,
        },
        config={"callbacks": [tracer]},
        stream_mode="updates",
    ):
        node_name = list(event.keys())[0]

        if node_name == "agent":
            msg = event["agent"]["messages"][0]
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc["name"]
                    args = tc["args"]
                    detail = args.get("url") or args.get("query") or args.get("text") or str(args)
                    payload = json.dumps({"type": "step", "tool": tool_name, "detail": detail})
                    yield f"data: {payload}\n\n"
            else:
                payload = json.dumps({"type": "report", "content": msg.content})
                yield f"data: {payload}\n\n"

        elif node_name == "tools":
            payload = json.dumps({"type": "tool_done"})
            yield f"data: {payload}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.post("/research")
def research(request: ResearchRequest):
    return StreamingResponse(
        stream_research(request.company),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}
