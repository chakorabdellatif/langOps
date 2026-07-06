"""Minimal instrumented LangGraph app — demo and end-to-end smoke test.

A two-node graph (plan → act) with one LLM call and one tool call, wrapped by
``langops.instrument``. Runs with no API key (uses a deterministic fake chat
model); swap in `ChatOpenAI(...)` for the real thing.

    docker compose up            # in the repo root: full LangOps stack
    pip install -e ../../sdk
    python main.py               # spans export to localhost:4317

With the stack running, the execution appears in the dashboard at
http://localhost:3000. Without it, the graph still runs cleanly — telemetry
export just fails quietly in the background.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

import langops


@tool
def word_count(text: str) -> int:
    """Count the words in a piece of text."""
    return len(text.split())


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    count: int


_model = GenericFakeChatModel(messages=iter([AIMessage(content="Here is a concise answer.")]))


def plan(state: State) -> dict:
    response = _model.invoke(state["messages"])
    return {"messages": [response]}


def act(state: State) -> dict:
    last = state["messages"][-1].content
    return {"count": word_count.invoke({"text": last})}


def build_graph():
    graph = StateGraph(State)
    graph.add_node("plan", plan)
    graph.add_node("act", act)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "act")
    graph.add_edge("act", END)
    return graph.compile()


def main() -> None:
    app = langops.instrument(build_graph())
    result = app.invoke(
        {"messages": [HumanMessage(content="Summarize LangOps in one line.")], "count": 0},
        config={"configurable": {"thread_id": "demo-1"}},
    )
    print("final answer:", result["messages"][-1].content)
    print("word count:", result["count"])


if __name__ == "__main__":
    main()
