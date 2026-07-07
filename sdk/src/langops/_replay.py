"""Execution replay (v0.2) — re-run a captured execution locally.

Replay fetches a recorded execution's input/config from the LangOps API and
re-invokes the *local* instrumented graph. The backend never runs user code —
replay happens in your environment, so external tools and APIs re-execute for
real. Replay is for experimentation (swap a model, edit the input, adjust
temperature), not deterministic time travel.

    from myapp import graph  # already langops.instrument(...)-ed
    langops.replay(graph, "0f9c…", model="gpt-5")

R1 (exact) and R2 (with overrides) are supported. Replaying from a checkpoint
or an arbitrary node (R3/R4) is future work.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from langops.instrumentation.runtime import ReplayInfo, replay_context

# The SDK truncation marker (mirrors capture.state); a truncated input cannot
# be faithfully replayed.
_TRUNCATED_MARKER = {"langops.truncated": True}


class ReplayError(RuntimeError):
    """Raised when an execution cannot be replayed (missing/truncated input)."""


def _fetch_execution(api_url: str, execution_id: str, timeout: float) -> dict[str, Any]:
    url = f"{api_url.rstrip('/')}/api/v1/executions/{execution_id}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 — trusted API URL
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise ReplayError(f"execution {execution_id} not found ({exc.code})") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ReplayError(f"could not reach LangOps API at {api_url}: {exc}") from exc


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
    config: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> Any:
    """Re-run ``execution_id`` on the local ``graph``, returning its output.

    Overrides (all optional): ``input`` replaces the recorded initial input;
    ``model`` / ``temperature`` are recorded on the new execution and passed via
    ``config["configurable"]`` (``langops_replay_model`` /
    ``langops_replay_temperature``) for apps that honour them. A fresh thread is
    used unless ``same_thread=True``.
    """
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
        return graph.invoke(run_input, cfg or None)
    finally:
        replay_context.reset(token)
