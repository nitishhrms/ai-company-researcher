from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ResearchState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    company: str
    steps: int  # counts agent node executions — used for max iterations guard
