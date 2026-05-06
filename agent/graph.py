from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from .state import ResearchState
from .tools import get_tools
from .prompts import SYSTEM_PROMPT


MAX_STEPS = 15


def build_graph():
    tools = get_tools()

    llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0).bind_tools(tools)

    # NODE 1: Agent — the LLM decides what to do next
    def agent_node(state: ResearchState):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm.invoke(messages)
        return {"messages": [response], "steps": state.get("steps", 0) + 1}

    # EDGE CONDITION: tool call → run tools | max steps hit → END | done → END

    def should_continue(state: ResearchState) -> str:
        if state.get("steps", 0) >= MAX_STEPS:
            print(f"  Max iterations ({MAX_STEPS}) reached — stopping agent.")
            return END
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    # NODE 2: Tools — executes whatever tool the LLM chose
    
    tool_node = ToolNode(tools)

    builder = StateGraph(ResearchState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)

    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", should_continue)
    builder.add_edge("tools", "agent")

    return builder.compile()
