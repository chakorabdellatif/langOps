"""Parsed OTLP spans → domain entities, per the semantic conventions.

Spans within a trace can arrive in any order and in separate batches, so the
mapper produces one MappedTrace per trace with whatever this batch contains;
IngestTelemetryService resolves cross-references (canonical execution id,
node linkage) against the database.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from uuid6 import uuid7

from langops_api.application.mappers import semconv
from langops_api.domain.entities import (
    Execution,
    LlmCall,
    LogRecord,
    NodeExecution,
    StateSnapshot,
    ToolCall,
)
from langops_api.domain.value_objects import CheckpointRef, ExecutionStatus, TokenUsage
from langops_api.infrastructure.otlp import ParsedEvent, ParsedSpan

# Deterministic ids for rows derived from span events (idempotent redelivery)
_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

# A placeholder — the service replaces it with the canonical DB execution id.
PENDING_EXECUTION_ID = uuid.UUID(int=0)


@dataclass
class GraphInfo:
    name: str
    topology: dict[str, Any] | None
    topology_hash: str


@dataclass
class MappedTrace:
    trace_id: str
    execution: Execution
    has_root_span: bool = False
    graph: GraphInfo | None = None
    nodes: list[NodeExecution] = field(default_factory=list)
    llm_calls: list[tuple[LlmCall, str | None]] = field(default_factory=list)  # + parent span id
    tool_calls: list[tuple[ToolCall, str | None]] = field(default_factory=list)
    snapshots: list[tuple[StateSnapshot, str | None]] = field(default_factory=list)
    logs: list[tuple[LogRecord, str | None]] = field(default_factory=list)


def _ts(nanos: int) -> datetime | None:
    return datetime.fromtimestamp(nanos / 1e9, tz=UTC) if nanos else None


def _duration_ms(span: ParsedSpan) -> int | None:
    if span.start_ns and span.end_ns:
        return max(0, int((span.end_ns - span.start_ns) / 1e6))
    return None


def _status(span: ParsedSpan) -> ExecutionStatus:
    return ExecutionStatus.FAILED if span.status_code == "ERROR" else ExecutionStatus.SUCCEEDED


def _error(span: ParsedSpan) -> dict[str, Any] | None:
    for event in span.events:
        if event.name == semconv.EVENT_EXCEPTION:
            return {
                "type": event.attributes.get(semconv.EXCEPTION_TYPE),
                "message": event.attributes.get(semconv.EXCEPTION_MESSAGE),
                "stack": event.attributes.get(semconv.EXCEPTION_STACKTRACE),
            }
    if span.status_code == "ERROR":
        return {"type": None, "message": span.status_message or "unknown error", "stack": None}
    return None


def _payload(event: ParsedEvent) -> Any:
    raw = event.attributes.get(semconv.PAYLOAD)
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw


def _event_payload(span: ParsedSpan, name: str) -> Any:
    for event in span.events:
        if event.name == name:
            return _payload(event)
    return None


def _stable_id(*parts: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, ":".join(parts))


def map_spans(spans: list[ParsedSpan]) -> list[MappedTrace]:
    traces: dict[str, MappedTrace] = {}
    for span in spans:
        trace = traces.get(span.trace_id)
        if trace is None:
            trace = MappedTrace(
                trace_id=span.trace_id,
                execution=Execution(
                    id=uuid7(),
                    project_id=PENDING_EXECUTION_ID,  # service sets the real project
                    trace_id=span.trace_id,
                ),
            )
            traces[span.trace_id] = trace
        _map_span(trace, span)
    return list(traces.values())


def _map_span(trace: MappedTrace, span: ParsedSpan) -> None:
    kind = span.attributes.get(semconv.KIND)
    if kind == semconv.KIND_EXECUTION:
        _map_execution(trace, span)
    elif kind == semconv.KIND_NODE:
        _map_node(trace, span)
    elif kind == semconv.KIND_LLM:
        _map_llm(trace, span)
    elif kind == semconv.KIND_TOOL:
        _map_tool(trace, span)
    # Spans without a langops.kind (foreign instrumentation) are ignored.

    _map_exception_logs(trace, span)


def _map_execution(trace: MappedTrace, span: ParsedSpan) -> None:
    trace.has_root_span = True
    execution = trace.execution
    execution.status = _status(span) if span.end_ns else ExecutionStatus.RUNNING
    execution.error = _error(span)
    execution.input = _event_payload(span, semconv.EVENT_EXECUTION_INPUT)
    execution.output = _event_payload(span, semconv.EVENT_EXECUTION_OUTPUT)
    execution.started_at = _ts(span.start_ns)
    execution.ended_at = _ts(span.end_ns)
    execution.duration_ms = _duration_ms(span)
    execution.sdk_version = span.resource.get(semconv.SDK_VERSION)
    execution.checkpoint = CheckpointRef(
        thread_id=span.attributes.get(semconv.THREAD_ID),
        checkpoint_id=span.attributes.get(semconv.CHECKPOINT_ID),
        parent_checkpoint_id=span.attributes.get(semconv.CHECKPOINT_PARENT_ID),
        resumed=bool(span.attributes.get(semconv.CHECKPOINT_RESUMED, False)),
    )

    graph_name = span.attributes.get(semconv.GRAPH_NAME)
    if graph_name:
        topology = _event_payload(span, semconv.EVENT_GRAPH_TOPOLOGY)
        trace.graph = GraphInfo(
            name=str(graph_name),
            topology=topology if isinstance(topology, dict) else None,
            topology_hash=str(span.attributes.get(semconv.GRAPH_TOPOLOGY_HASH, "")),
        )


def _map_node(trace: MappedTrace, span: ParsedSpan) -> None:
    category = span.attributes.get(semconv.NODE_CATEGORY)
    node = NodeExecution(
        id=_stable_id("node", span.span_id),
        execution_id=PENDING_EXECUTION_ID,
        span_id=span.span_id,
        parent_span_id=span.parent_span_id,
        node_name=str(span.attributes.get(semconv.NODE_NAME, span.name)),
        sequence=int(span.attributes.get(semconv.NODE_SEQUENCE, 0)),
        status=_status(span),
        retry_count=int(span.attributes.get(semconv.NODE_RETRY_COUNT, 0)),
        error=_error(span),
        started_at=_ts(span.start_ns),
        ended_at=_ts(span.end_ns),
        duration_ms=_duration_ms(span),
        category=str(category) if category else None,
    )
    trace.nodes.append(node)

    for event in span.events:
        if event.name in (
            semconv.EVENT_STATE_INPUT,
            semconv.EVENT_STATE_OUTPUT,
            semconv.EVENT_STATE_SNAPSHOT,
        ):
            kind = "input" if event.name == semconv.EVENT_STATE_INPUT else "output"
            state = _payload(event)
            snapshot = StateSnapshot(
                id=_stable_id("snapshot", span.span_id, event.name),
                execution_id=PENDING_EXECUTION_ID,
                node_execution_id=None,  # service links via span_id
                kind=kind,
                state=state,
                diff=None,  # recomputed server-side by the ingest service
                size_bytes=int(event.attributes.get(semconv.STATE_SIZE_BYTES, 0)),
                message_count=(
                    int(event.attributes[semconv.STATE_MESSAGE_COUNT])
                    if semconv.STATE_MESSAGE_COUNT in event.attributes
                    else None
                ),
                created_at=_ts(event.timestamp_ns) or _ts(span.end_ns),
            )
            trace.snapshots.append((snapshot, span.span_id))


def _map_llm(trace: MappedTrace, span: ParsedSpan) -> None:
    usage = TokenUsage(
        input_tokens=int(span.attributes.get(semconv.GEN_AI_USAGE_INPUT_TOKENS, 0)),
        output_tokens=int(span.attributes.get(semconv.GEN_AI_USAGE_OUTPUT_TOKENS, 0)),
    )
    call = LlmCall(
        id=_stable_id("llm", span.span_id),
        execution_id=PENDING_EXECUTION_ID,
        span_id=span.span_id,
        provider=span.attributes.get(semconv.GEN_AI_SYSTEM),
        model=span.attributes.get(semconv.GEN_AI_RESPONSE_MODEL)
        or span.attributes.get(semconv.GEN_AI_REQUEST_MODEL),
        messages=_event_payload(span, semconv.EVENT_LLM_MESSAGES),
        params=_event_payload(span, semconv.EVENT_LLM_PARAMS),
        response=_event_payload(span, semconv.EVENT_LLM_RESPONSE),
        tokens=usage,
        latency_ms=_duration_ms(span),
        started_at=_ts(span.start_ns),
        error=_error(span),
    )
    trace.llm_calls.append((call, span.parent_span_id))


def _map_tool(trace: MappedTrace, span: ParsedSpan) -> None:
    call = ToolCall(
        id=_stable_id("tool", span.span_id),
        execution_id=PENDING_EXECUTION_ID,
        span_id=span.span_id,
        tool_name=str(span.attributes.get(semconv.TOOL_NAME, span.name)),
        input=_event_payload(span, semconv.EVENT_TOOL_INPUT),
        output=_event_payload(span, semconv.EVENT_TOOL_OUTPUT),
        status=_status(span),
        error=_error(span),
        duration_ms=_duration_ms(span),
        started_at=_ts(span.start_ns),
    )
    trace.tool_calls.append((call, span.parent_span_id))


def _map_exception_logs(trace: MappedTrace, span: ParsedSpan) -> None:
    is_node = span.attributes.get(semconv.KIND) == semconv.KIND_NODE
    for index, event in enumerate(span.events):
        if event.name != semconv.EVENT_EXCEPTION:
            continue
        record = LogRecord(
            id=_stable_id("log", span.span_id, str(index)),
            execution_id=PENDING_EXECUTION_ID,
            level="error",
            message=str(event.attributes.get(semconv.EXCEPTION_MESSAGE, "error")),
            stack_trace=event.attributes.get(semconv.EXCEPTION_STACKTRACE),
            attributes={"exception.type": event.attributes.get(semconv.EXCEPTION_TYPE)},
            timestamp=_ts(event.timestamp_ns) or _ts(span.end_ns),
        )
        trace.logs.append((record, span.span_id if is_node else None))
