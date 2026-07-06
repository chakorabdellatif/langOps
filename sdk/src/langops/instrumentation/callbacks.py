"""LangChain callback handler → node, LLM, and tool spans.

Injected into the run config by the graph wrapper. Maps LangChain/LangGraph
runtime events onto OTel spans, wiring parent/child by ``run_id`` so the span
tree mirrors the execution tree (including subgraphs). Every handler method is
wrapped so an internal error logs once and drops the datum — it never
propagates into the host graph.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from langops import semconv
from langops.config import LangOpsConfig
from langops.instrumentation.runtime import add_payload_event

logger = logging.getLogger("langops")


def _parse_sequence(tags: list[str] | None) -> int:
    for tag in tags or []:
        if tag.startswith("graph:step:"):
            try:
                return int(tag.rsplit(":", 1)[1])
            except ValueError:
                return 0
    return 0


def _first(*values: Any) -> Any:
    for value in values:
        if value:
            return value
    return None


class LangOpsCallbackHandler(BaseCallbackHandler):
    def __init__(
        self,
        tracer: trace.Tracer,
        execution_id: str,
        root_span: Span,
        config: LangOpsConfig,
    ) -> None:
        self._tracer = tracer
        self._execution_id = execution_id
        self._root_span = root_span
        self._config = config
        self._spans: dict[UUID, Span] = {}
        self._retries: dict[tuple[str, int], int] = {}
        self._warned: set[str] = set()

    # ── failure policy ─────────────────────────────────────────────────

    def _warn_once(self, where: str, error: BaseException) -> None:
        if where not in self._warned:
            self._warned.add(where)
            logger.warning("langops: dropped telemetry in %s (%s)", where, type(error).__name__)

    def _start_span(
        self, name: str, run_id: UUID, parent_run_id: UUID | None, attributes: dict[str, Any]
    ) -> Span:
        parent = self._spans.get(parent_run_id) if parent_run_id else None
        context = trace.set_span_in_context(parent or self._root_span)
        span = self._tracer.start_span(name=name, context=context, attributes=attributes)
        self._spans[run_id] = span
        return span

    def _finish(self, run_id: UUID, error: BaseException | None = None) -> Span | None:
        span = self._spans.pop(run_id, None)
        if span is None:
            return None
        if error is not None:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR))
        else:
            span.set_status(Status(StatusCode.OK))
        return span

    # ── node spans ─────────────────────────────────────────────────────

    def on_chain_start(
        self,
        serialized: Any,
        inputs: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            node_name = (metadata or {}).get("langgraph_node")
            if not node_name:
                return  # the graph run itself / internal runnables — not a node
            sequence = _parse_sequence(tags)
            retry_key = (node_name, sequence)
            retry_count = self._retries.get(retry_key, 0)
            self._retries[retry_key] = retry_count + 1
            span = self._start_span(
                node_name,
                run_id,
                parent_run_id,
                {
                    semconv.KIND: semconv.Kind.NODE,
                    semconv.EXECUTION_ID: self._execution_id,
                    semconv.NODE_NAME: node_name,
                    semconv.NODE_SEQUENCE: sequence,
                    semconv.NODE_RETRY_COUNT: retry_count,
                },
            )
            add_payload_event(
                span, semconv.EVENT_STATE_INPUT, inputs, self._config, with_message_count=True
            )
        except Exception as error:  # noqa: BLE001
            self._warn_once("on_chain_start", error)

    def on_chain_end(self, outputs: Any, *, run_id: UUID, **kwargs: Any) -> None:
        try:
            span = self._finish(run_id)
            if span is None:
                return
            add_payload_event(
                span, semconv.EVENT_STATE_OUTPUT, outputs, self._config, with_message_count=True
            )
            span.end()
        except Exception as error:  # noqa: BLE001
            self._warn_once("on_chain_end", error)

    def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        try:
            span = self._finish(run_id, error)
            if span is not None:
                span.end()
        except Exception as inner:  # noqa: BLE001
            self._warn_once("on_chain_error", inner)

    # ── LLM spans ──────────────────────────────────────────────────────

    def on_chat_model_start(
        self,
        serialized: Any,
        messages: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._llm_start(serialized, messages, run_id, parent_run_id, metadata, kwargs)

    def on_llm_start(
        self,
        serialized: Any,
        prompts: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._llm_start(serialized, prompts, run_id, parent_run_id, metadata, kwargs)

    def _llm_start(
        self,
        serialized: Any,
        messages: Any,
        run_id: UUID,
        parent_run_id: UUID | None,
        metadata: dict[str, Any] | None,
        kwargs: dict[str, Any],
    ) -> None:
        try:
            params = kwargs.get("invocation_params") or {}
            metadata = metadata or {}
            provider = _first(metadata.get("ls_provider"), params.get("_type"))
            model = _first(
                metadata.get("ls_model_name"), params.get("model"), params.get("model_name")
            )
            attributes: dict[str, Any] = {
                semconv.KIND: semconv.Kind.LLM,
                semconv.EXECUTION_ID: self._execution_id,
            }
            if provider:
                attributes[semconv.GEN_AI_SYSTEM] = provider
            if model:
                attributes[semconv.GEN_AI_REQUEST_MODEL] = model
            span = self._start_span(str(model or "llm"), run_id, parent_run_id, attributes)
            add_payload_event(span, semconv.EVENT_LLM_MESSAGES, messages, self._config)
            if params:
                add_payload_event(span, semconv.EVENT_LLM_PARAMS, params, self._config)
        except Exception as error:  # noqa: BLE001
            self._warn_once("on_llm_start", error)

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        try:
            span = self._finish(run_id)
            if span is None:
                return
            usage = _extract_usage(response)
            if usage:
                span.set_attribute(semconv.GEN_AI_USAGE_INPUT_TOKENS, usage[0])
                span.set_attribute(semconv.GEN_AI_USAGE_OUTPUT_TOKENS, usage[1])
            model = _extract_response_model(response)
            if model:
                span.set_attribute(semconv.GEN_AI_RESPONSE_MODEL, model)
            add_payload_event(span, semconv.EVENT_LLM_RESPONSE, response, self._config)
            span.end()
        except Exception as error:  # noqa: BLE001
            self._warn_once("on_llm_end", error)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        try:
            span = self._finish(run_id, error)
            if span is not None:
                span.end()
        except Exception as inner:  # noqa: BLE001
            self._warn_once("on_llm_error", inner)

    # ── tool spans ─────────────────────────────────────────────────────

    def on_tool_start(
        self,
        serialized: Any,
        input_str: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            tool_name = (serialized or {}).get("name") or "tool"
            span = self._start_span(
                tool_name,
                run_id,
                parent_run_id,
                {
                    semconv.KIND: semconv.Kind.TOOL,
                    semconv.EXECUTION_ID: self._execution_id,
                    semconv.TOOL_NAME: tool_name,
                },
            )
            add_payload_event(span, semconv.EVENT_TOOL_INPUT, input_str, self._config)
        except Exception as error:  # noqa: BLE001
            self._warn_once("on_tool_start", error)

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        try:
            span = self._finish(run_id)
            if span is None:
                return
            add_payload_event(span, semconv.EVENT_TOOL_OUTPUT, output, self._config)
            span.end()
        except Exception as error:  # noqa: BLE001
            self._warn_once("on_tool_end", error)

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        try:
            span = self._finish(run_id, error)
            if span is not None:
                span.end()
        except Exception as inner:  # noqa: BLE001
            self._warn_once("on_tool_error", inner)


def _extract_usage(response: Any) -> tuple[int, int] | None:
    """Return (input_tokens, output_tokens) from an LLMResult, if present."""
    # Preferred: usage_metadata on the chat generation's message.
    try:
        message = response.generations[0][0].message
        usage = getattr(message, "usage_metadata", None)
        if usage:
            return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
    except (AttributeError, IndexError, TypeError):
        pass
    # Fallback: token_usage in llm_output.
    llm_output = getattr(response, "llm_output", None) or {}
    usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
    if usage:
        return (
            int(usage.get("prompt_tokens", usage.get("input_tokens", 0))),
            int(usage.get("completion_tokens", usage.get("output_tokens", 0))),
        )
    return None


def _extract_response_model(response: Any) -> str | None:
    llm_output = getattr(response, "llm_output", None) or {}
    model = llm_output.get("model_name") or llm_output.get("model")
    return str(model) if model else None
