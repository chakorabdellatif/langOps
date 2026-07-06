"""CompiledGraph wrapper — the execution root span.

``instrument_graph`` monkeypatches the graph's four entrypoints
(invoke/ainvoke/stream/astream) in place (they are plain methods on the
compiled Pregel object) and wraps the checkpointer if one is attached. Each
entrypoint opens the execution root span, captures topology once, extracts
thread/checkpoint metadata, injects the callback handler, records input/output,
and closes the span. If telemetry setup fails, the original graph runs
unwrapped — the host app is never affected.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import uuid4

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Status, StatusCode

from langops import semconv
from langops.config import LangOpsConfig
from langops.instrumentation.callbacks import LangOpsCallbackHandler
from langops.instrumentation.checkpointer import InstrumentedCheckpointer
from langops.instrumentation.runtime import RunContext, add_payload_event, current_run

logger = logging.getLogger("langops")


def instrument_graph(graph: Any, sdk_config: LangOpsConfig, provider: TracerProvider) -> Any:
    from langops import __version__

    tracer = provider.get_tracer("langops", __version__)

    # Wrap the checkpointer (composition) for authoritative checkpoint lineage.
    inner_checkpointer = getattr(graph, "checkpointer", None)
    if inner_checkpointer is not None and not isinstance(
        inner_checkpointer, InstrumentedCheckpointer
    ):
        try:
            graph.checkpointer = InstrumentedCheckpointer(inner_checkpointer)
        except Exception:  # noqa: BLE001 — checkpointer wrapping is best-effort
            logger.warning("langops: could not wrap checkpointer; checkpoint lineage unavailable")

    orig_invoke = graph.invoke
    orig_ainvoke = graph.ainvoke
    orig_stream = graph.stream
    orig_astream = graph.astream

    def _begin(cfg: Any) -> tuple[RunContext, Any, Any] | None:
        # Re-entrancy guard: LangGraph's invoke/ainvoke delegate internally to
        # self.stream/self.astream, which are also patched. When a run is
        # already active the inner call passes through unwrapped — the handler
        # is already in the config, so nothing is double-counted.
        if current_run.get() is not None:
            return None
        try:
            execution_id = str(uuid4())
            root = tracer.start_span(
                "execution",
                attributes={
                    semconv.KIND: semconv.Kind.EXECUTION,
                    semconv.EXECUTION_ID: execution_id,
                },
            )
            run = RunContext(execution_id=execution_id, root_span=root)
            token = current_run.set(run)

            graph_name = sdk_config.graph_name or getattr(graph, "name", None) or "graph"
            root.set_attribute(semconv.GRAPH_NAME, graph_name)
            topology, topology_hash = _topology(graph)
            if topology_hash:
                root.set_attribute(semconv.GRAPH_TOPOLOGY_HASH, topology_hash)
            if topology is not None:
                add_payload_event(root, semconv.EVENT_GRAPH_TOPOLOGY, topology, sdk_config)

            configurable = (cfg or {}).get("configurable", {}) or {}
            thread_id = configurable.get("thread_id")
            if thread_id:
                root.set_attribute(semconv.THREAD_ID, thread_id)
            resumed, parent_checkpoint = _detect_resumed(graph, cfg)
            root.set_attribute(semconv.CHECKPOINT_RESUMED, resumed)
            if parent_checkpoint:
                run.parent_checkpoint_id = parent_checkpoint

            handler = LangOpsCallbackHandler(tracer, execution_id, root, sdk_config)
            return run, token, _inject(cfg, handler)
        except Exception:  # noqa: BLE001 — never block the run on telemetry setup
            logger.warning("langops: instrumentation setup failed; running graph unwrapped")
            return None

    def _end(run: RunContext, token: Any, error: BaseException | None = None) -> None:
        root = run.root_span
        try:
            if run.checkpoint_id:
                root.set_attribute(semconv.CHECKPOINT_ID, run.checkpoint_id)
            if run.parent_checkpoint_id:
                root.set_attribute(semconv.CHECKPOINT_PARENT_ID, run.parent_checkpoint_id)
            if error is not None:
                root.record_exception(error)
                root.set_status(Status(StatusCode.ERROR))
            else:
                root.set_status(Status(StatusCode.OK))
            root.end()
        finally:
            current_run.reset(token)

    def invoke(input: Any, config: Any = None, **kwargs: Any) -> Any:
        begun = _begin(config)
        if begun is None:
            return orig_invoke(input, config, **kwargs)
        run, token, new_cfg = begun
        try:
            add_payload_event(run.root_span, semconv.EVENT_EXECUTION_INPUT, input, sdk_config)
            result = orig_invoke(input, new_cfg, **kwargs)
            add_payload_event(run.root_span, semconv.EVENT_EXECUTION_OUTPUT, result, sdk_config)
            _end(run, token)
            return result
        except Exception as error:
            _end(run, token, error)
            raise

    async def ainvoke(input: Any, config: Any = None, **kwargs: Any) -> Any:
        begun = _begin(config)
        if begun is None:
            return await orig_ainvoke(input, config, **kwargs)
        run, token, new_cfg = begun
        try:
            add_payload_event(run.root_span, semconv.EVENT_EXECUTION_INPUT, input, sdk_config)
            result = await orig_ainvoke(input, new_cfg, **kwargs)
            add_payload_event(run.root_span, semconv.EVENT_EXECUTION_OUTPUT, result, sdk_config)
            _end(run, token)
            return result
        except Exception as error:
            _end(run, token, error)
            raise

    def stream(input: Any, config: Any = None, **kwargs: Any) -> Iterator[Any]:
        begun = _begin(config)
        if begun is None:
            yield from orig_stream(input, config, **kwargs)
            return
        run, token, new_cfg = begun
        add_payload_event(run.root_span, semconv.EVENT_EXECUTION_INPUT, input, sdk_config)
        last: Any = None
        try:
            for chunk in orig_stream(input, new_cfg, **kwargs):
                last = chunk
                yield chunk
        except Exception as error:
            _end(run, token, error)
            raise
        add_payload_event(run.root_span, semconv.EVENT_EXECUTION_OUTPUT, last, sdk_config)
        _end(run, token)

    async def astream(input: Any, config: Any = None, **kwargs: Any) -> AsyncIterator[Any]:
        begun = _begin(config)
        if begun is None:
            async for chunk in orig_astream(input, config, **kwargs):
                yield chunk
            return
        run, token, new_cfg = begun
        add_payload_event(run.root_span, semconv.EVENT_EXECUTION_INPUT, input, sdk_config)
        last: Any = None
        try:
            async for chunk in orig_astream(input, new_cfg, **kwargs):
                last = chunk
                yield chunk
        except Exception as error:
            _end(run, token, error)
            raise
        add_payload_event(run.root_span, semconv.EVENT_EXECUTION_OUTPUT, last, sdk_config)
        _end(run, token)

    graph.invoke = invoke
    graph.ainvoke = ainvoke
    graph.stream = stream
    graph.astream = astream
    return graph


def _inject(cfg: Any, handler: LangOpsCallbackHandler) -> dict[str, Any]:
    new_cfg = dict(cfg) if cfg else {}
    callbacks = new_cfg.get("callbacks")
    if callbacks is None:
        new_cfg["callbacks"] = [handler]
    elif isinstance(callbacks, list):
        new_cfg["callbacks"] = [*callbacks, handler]
    else:  # a CallbackManager or single handler
        new_cfg["callbacks"] = [callbacks, handler]
    return new_cfg


def _topology(graph: Any) -> tuple[dict[str, Any] | None, str | None]:
    try:
        drawable = graph.get_graph()
        nodes = sorted(str(n) for n in drawable.nodes)
        edges = sorted((str(e.source), str(e.target)) for e in drawable.edges)
        topology = {"nodes": nodes, "edges": [list(e) for e in edges]}
        digest = hashlib.sha256(json.dumps(topology, sort_keys=True).encode()).hexdigest()[:16]
        return topology, digest
    except Exception:  # noqa: BLE001
        return None, None


def _detect_resumed(graph: Any, cfg: Any) -> tuple[bool, str | None]:
    """True when a checkpoint already exists for the thread before this run."""
    try:
        if getattr(graph, "checkpointer", None) is None:
            return False, None
        snapshot = graph.get_state(cfg)
        if snapshot and getattr(snapshot, "values", None):
            configurable = (getattr(snapshot, "config", None) or {}).get("configurable", {})
            return True, configurable.get("checkpoint_id")
    except Exception:  # noqa: BLE001
        pass
    return False, None
