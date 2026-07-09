"""Execution replay — re-run a captured execution locally.

Replay fetches a recorded execution's input/config from the LangOps API and
re-invokes the *local* instrumented graph (the backend never runs user code).

Two modes:

- **Live replay** (default): external tools/APIs and the LLM re-execute for
  real — experimentation (swap a model, edit the input, adjust temperature).

    langops.replay(graph, "0f9c…", model="gpt-5")

- **Cached replay** (``stub_llm`` / ``stub_tools``): recorded LLM/tool outputs
  are served from the trace, so the run is deterministic and costs no tokens —
  ideal for debugging graph logic without paying for inference.

    langops.replay(graph, "0f9c…", stub_llm=True)

Replaying from a checkpoint or an arbitrary node (R3/R4) is future work.
"""

from __future__ import annotations

import contextlib
import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

from langops.instrumentation.runtime import ReplayInfo, replay_context

# The SDK truncation marker (mirrors capture.state); a truncated input cannot
# be faithfully replayed.
_TRUNCATED_MARKER = {"langops.truncated": True}


class ReplayError(RuntimeError):
    """Raised when an execution cannot be replayed (missing/truncated input)."""


def _fetch_json(api_url: str, path: str, timeout: float) -> Any:
    url = f"{api_url.rstrip('/')}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 — trusted API URL
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise ReplayError(f"request failed ({exc.code}): {path}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ReplayError(f"could not reach LangOps API at {api_url}: {exc}") from exc


def _fetch_execution(api_url: str, execution_id: str, timeout: float) -> dict[str, Any]:
    result = _fetch_json(api_url, f"/api/v1/executions/{execution_id}", timeout)
    return result if isinstance(result, dict) else {}


def _is_truncated(value: Any) -> bool:
    return value == _TRUNCATED_MARKER or (
        isinstance(value, dict) and value.get("langops.truncated") is True
    )


def replay(
    graph: Any,
    execution_id: str,
    *,
    api_url: str = "http://localhost:8000",
    input: Any = None,
    model: str | None = None,
    temperature: float | None = None,
    same_thread: bool = False,
    stub_llm: bool = False,
    stub_tools: list[Any] | None = None,
    on_miss: str = "execute",
    config: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> Any:
    """Re-run ``execution_id`` on the local ``graph``, returning its output.

    Overrides (all optional): ``input`` replaces the recorded initial input;
    ``model`` / ``temperature`` are recorded on the new execution and passed via
    ``config["configurable"]``. A fresh thread is used unless ``same_thread``.

    Cached replay (deterministic, zero-token): ``stub_llm=True`` serves the
    recorded LLM responses in order (via LangChain's global cache) so no model
    is called; ``stub_tools=[tool, …]`` serves recorded tool outputs for the
    given tool objects. ``on_miss`` is ``"execute"`` (run for real when the run
    diverges from the recording) or ``"fail"`` (strict reproducibility).
    """
    if stub_llm and model is not None:
        raise ReplayError(
            "cannot combine stub_llm with a model override — replaying the old model's "
            "cached answers contradicts swapping the model"
        )
    if on_miss not in ("execute", "fail"):
        raise ReplayError("on_miss must be 'execute' or 'fail'")

    recorded = _fetch_execution(api_url, execution_id, timeout)
    recorded_input = recorded.get("input")

    if input is None and _is_truncated(recorded_input):
        raise ReplayError(
            "recorded input was truncated at capture time; pass input=... to replay explicitly"
        )
    run_input = input if input is not None else recorded_input
    if run_input is None:
        raise ReplayError(f"execution {execution_id} has no recorded input to replay")

    overrides: dict[str, Any] = {}
    if input is not None:
        overrides["input"] = "custom"
    if model is not None:
        overrides["model"] = model
    if temperature is not None:
        overrides["temperature"] = temperature
    if stub_llm or stub_tools:
        overrides["stubbed"] = {
            "llm": bool(stub_llm),
            "tools": [getattr(t, "name", str(t)) for t in (stub_tools or [])],
        }

    cfg = dict(config or {})
    configurable = dict(cfg.get("configurable") or {})
    if same_thread and recorded.get("thread_id"):
        configurable["thread_id"] = recorded["thread_id"]
    if model is not None:
        configurable["langops_replay_model"] = model
    if temperature is not None:
        configurable["langops_replay_temperature"] = temperature
    if configurable:
        cfg["configurable"] = configurable

    token = replay_context.set(ReplayInfo(replay_of=execution_id, overrides=overrides))
    try:
        with _stubbed(api_url, execution_id, stub_llm, stub_tools, on_miss, timeout):
            return graph.invoke(run_input, cfg or None)
    finally:
        replay_context.reset(token)


@contextlib.contextmanager
def _stubbed(
    api_url: str,
    execution_id: str,
    stub_llm: bool,
    stub_tools: list[Any] | None,
    on_miss: str,
    timeout: float,
) -> Iterator[None]:
    """Install the recorded LLM cache + tool stubs for the duration of a replay,
    restoring the process state afterwards (always, even on error)."""
    if not stub_llm and not stub_tools:
        yield
        return

    from langops._stubs import ToolStub, build_llm_cache

    restore_cache: contextlib.AbstractContextManager[Any] = contextlib.nullcontext()
    if stub_llm:
        from langchain_core.globals import get_llm_cache, set_llm_cache

        calls = _fetch_json(api_url, f"/api/v1/executions/{execution_id}/llm-calls", timeout)
        for call in calls:
            if _is_truncated(call.get("response")):
                raise ReplayError(
                    "a recorded LLM response was truncated at capture time; cannot stub it "
                    "(replay without --stub-llm, or re-capture with a larger payload limit)"
                )
        cache = build_llm_cache(calls, on_miss=on_miss)
        previous = get_llm_cache()
        set_llm_cache(cache)
        restore_cache = _Restore(lambda: set_llm_cache(previous))

    originals: list[tuple[Any, Any]] = []
    if stub_tools:
        tool_calls = _fetch_json(api_url, f"/api/v1/executions/{execution_id}/tool-calls", timeout)
        stub = ToolStub(tool_calls, on_miss=on_miss)
        for tool in stub_tools:
            func = getattr(tool, "func", None)
            if func is None:
                continue  # not a wrappable StructuredTool — skip (runs for real)
            originals.append((tool, func))
            tool.func = _tool_wrapper(tool, func, stub)

    try:
        with restore_cache:
            yield
    finally:
        for tool, func in originals:
            tool.func = func


def _tool_wrapper(tool: Any, original: Any, stub: Any) -> Any:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        tool_input = kwargs if kwargs else (args[0] if args else None)
        hit, output = stub.output_for(getattr(tool, "name", "tool"), tool_input)
        return output if hit else original(*args, **kwargs)

    return wrapper


class _Restore:
    def __init__(self, fn: Any) -> None:
        self._fn = fn

    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: Any) -> None:
        self._fn()
