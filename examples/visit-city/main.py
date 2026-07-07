"""Visit City — a multi-agent LangGraph app, observed with one line of LangOps.

Ask about a city and four agents collaborate:

    weather  → current conditions from Open-Meteo (no API key)
    history  → a short historical summary          (gpt-4o-mini)
    economy  → key economic facts                  (gpt-4o-mini)
    summary  → organizes everything into a brief   (gpt-4o-mini)

The whole run is captured by LangOps — graph path, per-node state, every LLM and
tool call, tokens, and cost — from a single `langops.instrument(graph)`.

Results are cached in Redis by city: ask about the same city twice and the second
answer is served instantly, without re-running the agents.

    pip install -r examples/visit-city/requirements.txt
    export OPENAI_API_KEY=sk-...
    python examples/visit-city/main.py Paris Tokyo Cairo

Then open http://localhost:3000 — each city is a full execution in the dashboard.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Annotated, Any, TypedDict

import httpx
import redis
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

import langops

MODEL = "gpt-4o-mini"
cache = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

_llm: ChatOpenAI | None = None


def llm() -> ChatOpenAI:
    """Lazily construct the model (so importing this module needs no API key)."""
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model=MODEL, temperature=0.3)
    return _llm


@tool
def get_weather(city: str) -> dict[str, Any]:
    """Current weather for a city via Open-Meteo (free, no API key)."""
    geo = httpx.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1},
        timeout=10,
    ).json()
    if not geo.get("results"):
        return {"error": f"city not found: {city}"}
    loc = geo["results"][0]
    forecast = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "current": "temperature_2m,weather_code",
        },
        timeout=10,
    ).json()
    current = forecast.get("current", {})
    return {
        "city": loc["name"],
        "country": loc.get("country"),
        "temperature_c": current.get("temperature_2m"),
        "weather_code": current.get("weather_code"),
    }


class State(TypedDict):
    city: str
    messages: Annotated[list[BaseMessage], add_messages]
    weather: dict[str, Any]
    history: str
    economy: str
    report: str


def weather_agent(state: State) -> dict[str, Any]:
    return {"weather": get_weather.invoke({"city": state["city"]})}


def history_agent(state: State) -> dict[str, Any]:
    resp = llm().invoke(f"In 3 sentences, summarize the history of {state['city']}.")
    return {"history": resp.content, "messages": [resp]}


def economy_agent(state: State) -> dict[str, Any]:
    resp = llm().invoke(f"In 3 sentences, describe the economy of {state['city']}.")
    return {"economy": resp.content, "messages": [resp]}


def summary_agent(state: State) -> dict[str, Any]:
    prompt = (
        f"Write a concise traveler's brief for {state['city']}. Use these inputs:\n"
        f"- Weather: {state['weather']}\n- History: {state['history']}\n"
        f"- Economy: {state['economy']}"
    )
    resp = llm().invoke(prompt)
    return {"report": resp.content, "messages": [resp]}


def build_graph():  # type: ignore[no-untyped-def]
    graph = StateGraph(State)
    graph.add_node("weather", weather_agent)
    graph.add_node("history", history_agent)
    graph.add_node("economy", economy_agent)
    graph.add_node("summary", summary_agent)
    graph.add_edge(START, "weather")
    graph.add_edge("weather", "history")
    graph.add_edge("history", "economy")
    graph.add_edge("economy", "summary")
    graph.add_edge("summary", END)
    return graph.compile()


# One line: every execution of this graph is now observed by LangOps.
_graph = langops.instrument(
    build_graph(),
    langops.LangOpsConfig(service_name="visit-city", graph_name="visit-city"),
)


def _cache_get(key: str) -> dict[str, Any] | None:
    try:
        cached = cache.get(key)
        return json.loads(cached) if cached is not None else None
    except redis.RedisError:
        return None  # cache is a nice-to-have; never fail a run on Redis


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    try:
        cache.set(key, json.dumps(payload), ex=3600)  # 1-hour TTL
    except redis.RedisError:
        pass


def visit_city(city: str) -> dict[str, Any]:
    """Run the agents for a city, caching the result in Redis by city name."""
    key = f"visit-city:{city.lower()}"
    cached = _cache_get(key)
    if cached is not None:
        print(f"[cache hit]  {city} — served from Redis, agents skipped")
        return cached

    print(f"[cache miss] {city} — running the agents…")
    result = _graph.invoke(
        {"city": city, "messages": []},
        config={"configurable": {"thread_id": city.lower()}},
    )
    payload = {"city": city, "weather": result["weather"], "report": result["report"]}
    _cache_set(key, payload)
    return payload


def main() -> None:
    cities = sys.argv[1:] or ["Paris", "Tokyo", "Cairo"]
    for city in cities:
        result = visit_city(city)
        print(f"\n=== {city} ===")
        print(result["report"])
        print()

    # Re-visit the first city to show the Redis cache in action.
    print("--- re-visiting to demonstrate caching ---")
    visit_city(cities[0])


if __name__ == "__main__":
    main()
