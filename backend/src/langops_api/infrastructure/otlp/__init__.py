"""OTLP/HTTP payload parsing → normalized spans.

Two wire formats per the OTLP spec: protobuf (application/x-protobuf,
what the Collector sends) and JSON (application/json, hex-encoded ids).
Both normalize into ParsedSpan so the mapper has a single input shape.
Malformed input raises InvalidTelemetry (→ HTTP 400, never 500).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)

from langops_api.domain.errors import InvalidTelemetry

STATUS_CODES = {0: "UNSET", 1: "OK", 2: "ERROR"}


@dataclass
class ParsedEvent:
    name: str
    timestamp_ns: int
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedSpan:
    trace_id: str  # lowercase hex
    span_id: str
    parent_span_id: str | None
    name: str
    start_ns: int
    end_ns: int
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[ParsedEvent] = field(default_factory=list)
    status_code: str = "UNSET"
    status_message: str = ""
    resource: dict[str, Any] = field(default_factory=dict)


def parse_traces(body: bytes, content_type: str) -> list[ParsedSpan]:
    if "json" in content_type:
        import json

        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise InvalidTelemetry("Invalid OTLP/JSON payload", str(exc)) from exc
        return _parse_json(payload)
    return _parse_protobuf(body)


# ── protobuf ───────────────────────────────────────────────────────────


def _parse_protobuf(body: bytes) -> list[ParsedSpan]:
    request = ExportTraceServiceRequest()
    try:
        request.ParseFromString(body)
    except DecodeError as exc:
        raise InvalidTelemetry("Invalid OTLP protobuf payload", str(exc)) from exc

    spans: list[ParsedSpan] = []
    for resource_spans in request.resource_spans:
        resource = {kv.key: _pb_value(kv.value) for kv in resource_spans.resource.attributes}
        for scope_spans in resource_spans.scope_spans:
            for span in scope_spans.spans:
                spans.append(
                    ParsedSpan(
                        trace_id=span.trace_id.hex(),
                        span_id=span.span_id.hex(),
                        parent_span_id=span.parent_span_id.hex() or None,
                        name=span.name,
                        start_ns=span.start_time_unix_nano,
                        end_ns=span.end_time_unix_nano,
                        attributes={kv.key: _pb_value(kv.value) for kv in span.attributes},
                        events=[
                            ParsedEvent(
                                name=event.name,
                                timestamp_ns=event.time_unix_nano,
                                attributes={kv.key: _pb_value(kv.value) for kv in event.attributes},
                            )
                            for event in span.events
                        ],
                        status_code=STATUS_CODES.get(span.status.code, "UNSET"),
                        status_message=span.status.message,
                        resource=resource,
                    )
                )
    return spans


def _pb_value(value: Any) -> Any:
    kind = value.WhichOneof("value")
    if kind is None:
        return None
    if kind == "array_value":
        return [_pb_value(v) for v in value.array_value.values]
    if kind == "kvlist_value":
        return {kv.key: _pb_value(kv.value) for kv in value.kvlist_value.values}
    if kind == "bytes_value":
        return value.bytes_value.hex()
    return getattr(value, kind)


# ── JSON ───────────────────────────────────────────────────────────────


def _parse_json(payload: Any) -> list[ParsedSpan]:
    if not isinstance(payload, dict):
        raise InvalidTelemetry("OTLP/JSON payload must be an object")

    spans: list[ParsedSpan] = []
    for resource_spans in payload.get("resourceSpans", []):
        resource = _json_attributes(resource_spans.get("resource", {}).get("attributes", []))
        for scope_spans in resource_spans.get("scopeSpans", []):
            for span in scope_spans.get("spans", []):
                try:
                    spans.append(
                        ParsedSpan(
                            trace_id=str(span["traceId"]).lower(),
                            span_id=str(span["spanId"]).lower(),
                            parent_span_id=str(span["parentSpanId"]).lower()
                            if span.get("parentSpanId")
                            else None,
                            name=span.get("name", ""),
                            start_ns=int(span.get("startTimeUnixNano", 0)),
                            end_ns=int(span.get("endTimeUnixNano", 0)),
                            attributes=_json_attributes(span.get("attributes", [])),
                            events=[
                                ParsedEvent(
                                    name=event.get("name", ""),
                                    timestamp_ns=int(event.get("timeUnixNano", 0)),
                                    attributes=_json_attributes(event.get("attributes", [])),
                                )
                                for event in span.get("events", [])
                            ],
                            status_code=_json_status(span.get("status", {})),
                            status_message=span.get("status", {}).get("message", ""),
                            resource=resource,
                        )
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise InvalidTelemetry("Malformed span in OTLP/JSON payload", str(exc)) from exc
    return spans


def _json_status(status: dict[str, Any]) -> str:
    code = status.get("code", 0)
    if isinstance(code, str):  # e.g. "STATUS_CODE_ERROR"
        return code.removeprefix("STATUS_CODE_")
    return STATUS_CODES.get(int(code), "UNSET")


def _json_attributes(attributes: list[dict[str, Any]]) -> dict[str, Any]:
    return {item["key"]: _json_value(item.get("value", {})) for item in attributes if "key" in item}


def _json_value(value: dict[str, Any]) -> Any:
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "boolValue" in value:
        return bool(value["boolValue"])
    if "arrayValue" in value:
        return [_json_value(v) for v in value["arrayValue"].get("values", [])]
    if "kvlistValue" in value:
        return _json_attributes(value["kvlistValue"].get("values", []))
    if "bytesValue" in value:
        return value["bytesValue"]
    return None
