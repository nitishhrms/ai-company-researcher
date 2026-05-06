import os
import sys
from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage
from langchain_core.tracers.langchain import LangChainTracer
from langsmith import Client
from agent.graph import build_graph


def research_company(company: str):
    print(f"\nResearching: {company}")
    print("=" * 60)

    project = os.getenv("LANGCHAIN_PROJECT", "research-agent")
    tracer = LangChainTracer(project_name=project)

    graph = build_graph()
    step = 0
    final_report = ""

    for event in graph.stream(
        {
            "messages": [HumanMessage(content=f"Research the startup: {company}")],
            "company": company,
            "steps": 0,
        },
        config={"callbacks": [tracer]},
        stream_mode="updates",
    ):
        step += 1
        node_name = list(event.keys())[0]

        if node_name == "agent":
            msg = event["agent"]["messages"][0]
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc["name"]
                    args = tc["args"]
                    # print the most useful arg depending on the tool
                    detail = args.get("url") or args.get("query") or args.get("text") or str(args)
                    print(f"[Step {step}] {tool_name}: {detail!r}")
            else:
                print(f"[Step {step}] Writing final report...")
                final_report = msg.content

        elif node_name == "tools":
            print(f"[Step {step}] Tool result received")

    print("\n" + "=" * 60)
    print(final_report)
    print("=" * 60)

    # print LangSmith trace link after every run
    try:
        client = Client()
        runs = list(client.list_runs(project_name=project, limit=1))
        if runs:
            print(f"\nLangSmith trace: https://smith.langchain.com/runs/{runs[0].id}")
        else:
            print(f"\nLangSmith project: https://smith.langchain.com (project: {project})")
    except Exception:
        print(f"\nLangSmith project: https://smith.langchain.com (project: {project})")

    return final_report


if __name__ == "__main__":
    company = sys.argv[1] if len(sys.argv) > 1 else "Dex"
    research_company(company)
    os._exit(0)  # kill Playwright Node.js subprocess instantly, prevents EPIPE
