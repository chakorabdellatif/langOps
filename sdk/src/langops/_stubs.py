"""Cached-replay stubs (v0.1) — serve recorded LLM/tool outputs, zero-token.

LLM stubbing is generic: LangChain consults a process-global LLM cache before
every model call, so a cache that replays recorded generations *in order*
short-circuits every chat model without touching the user's graph. Tool
stubbing is explicit: the caller passes the tool objects to wrap (there is no
global tool cache, and tools invoked inside node functions can't be discovered
from a compiled graph).
"""

from __future__ import annotations

import json
import logging
from collections import deque
from collections.abc import Sequence
from typing import Any

from langchain_core.caches import BaseCache
from langchain_core.outputs import Generation

from langops.instrumentation.runtime import llm_stub_served

logger = logging.getLogger("langops")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _response_content(response: Any) -> str:
    """Best-effort extraction of the assistant text from a recorded response."""
    node = response
    for _ in range(6):  # bounded descent through the recorded LLMResult shape
        if isinstance(node, str):
            return node
        if isinstance(node, dict):
            for key in ("text", "content"):
                if isinstance(node.get(key), str):
                    return node[key]
            if "message" in node:
                node = node["message"]
                continue
            if "generations" in node:
                node = node["generations"]
                continue
        if isinstance(node, (list, tuple)) and node:
            node = node[0]
            continue
        break
    return ""


class ReplayLLMCache(BaseCache):
    """A LangChain ``BaseCache`` that replays recorded generations in order.

    It ignores the cache key entirely: recorded responses are served FIFO, which
    matches deterministic re-execution of the same graph on the same input. A
    miss (queue exhausted) either falls through to a real call (``on_miss
    == "execute"``) or raises (``"fail"``).
    """

    def __init__(self, recorded: list[dict[str, Any]], *, on_miss: str = "execute") -> None:
        # Each item: {content, input_tokens, output_tokens}.
        self._queue: deque[dict[str, Any]] = deque(recorded)
        self._on_miss = on_miss
        self.served = 0
        self.missed = 0

    def lookup(self, prompt: str, llm_string: str) -> Sequence[Generation] | None:
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration

        if not self._queue:
            self.missed += 1
            llm_stub_served.set(False)
            if self._on_miss == "fail":
                raise StubMiss(
                    "cached replay ran out of recorded LLM responses; the run diverged "
                    "from the recording (use on_miss='execute' to allow real calls)"
                )
            return None
        record = self._queue.popleft()
        self.served += 1
        llm_stub_served.set(True)
        message = AIMessage(
            content=record.get("content", ""),
            usage_metadata={
                "input_tokens": int(record.get("input_tokens", 0)),
                "output_tokens": int(record.get("output_tokens", 0)),
                "total_tokens": int(record.get("input_tokens", 0))
                + int(record.get("output_tokens", 0)),
            },
        )
        return [ChatGeneration(message=message)]

    def update(self, prompt: str, llm_string: str, return_val: Sequence[Generation]) -> None:
        return  # replay is read-only

    def clear(self, **kwargs: Any) -> None:
        self._queue.clear()


class StubMiss(RuntimeError):
    """Raised in strict mode when no recorded output matches a call."""


def build_llm_cache(llm_calls: list[dict[str, Any]], *, on_miss: str) -> ReplayLLMCache:
    recorded = [
        {
            "content": _response_content(call.get("response")),
            "input_tokens": call.get("input_tokens", 0),
            "output_tokens": call.get("output_tokens", 0),
        }
        for call in llm_calls
    ]
    return ReplayLLMCache(recorded, on_miss=on_miss)


class ToolStub:
    """Serves recorded tool outputs, matched by (tool name, canonical input)."""

    def __init__(self, tool_calls: list[dict[str, Any]], *, on_miss: str = "execute") -> None:
        self._by_name: dict[str, deque[dict[str, Any]]] = {}
        for call in tool_calls:
            self._by_name.setdefault(call["tool_name"], deque()).append(call)
        self._on_miss = on_miss

    def output_for(self, tool_name: str, tool_input: Any) -> tuple[bool, Any]:
        """Return (hit, output). On a miss, hit is False and output is None."""
        queue = self._by_name.get(tool_name)
        if not queue:
            return self._miss(tool_name)
        target = _canonical(tool_input)
        # Prefer an exact input match; else fall back to the next recorded call
        # in order (inputs may serialise slightly differently).
        for _ in range(len(queue)):
            call = queue[0]
            if _canonical(call.get("input")) == target:
                queue.popleft()
                return True, call.get("output")
            queue.rotate(-1)
        call = queue.popleft()
        return True, call.get("output")

    def _miss(self, tool_name: str) -> tuple[bool, Any]:
        if self._on_miss == "fail":
            raise StubMiss(f"no recorded output for tool {tool_name!r}")
        logger.warning("langops: no recorded output for tool %r; executing for real", tool_name)
        return False, None
