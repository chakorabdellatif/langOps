"""Span processor construction.

Async batched export via the stock OTel ``BatchSpanProcessor`` + OTLP/gRPC
exporter. Payload-size limiting happens at capture time (``capture/state.py``),
not here, so the processor stays standard and swappable.
"""

from __future__ import annotations

import os

from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from langops.config import LangOpsConfig


def build_processor(config: LangOpsConfig) -> SpanProcessor:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    api_key = config.api_key or os.getenv("LANGOPS_API_KEY")
    headers = (("authorization", f"Bearer {api_key}"),) if api_key else None
    exporter = OTLPSpanExporter(endpoint=config.endpoint, insecure=True, headers=headers)
    return BatchSpanProcessor(exporter)
