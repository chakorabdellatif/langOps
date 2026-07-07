"""Dedicated TracerProvider setup.

A private provider is built for LangOps — never the global one — so LangOps
coexists with any OpenTelemetry instrumentation the user already runs. Resource
attributes identify the service, SDK version, and project.
"""

import atexit

from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased, TraceIdRatioBased

from langops import __version__, semconv
from langops.config import LangOpsConfig
from langops.export.processors import build_processor


def build_tracer_provider(config: LangOpsConfig) -> TracerProvider:
    resource = Resource.create(
        {
            SERVICE_NAME: config.service_name,
            semconv.SDK_VERSION: __version__,
            semconv.PROJECT: config.project,
        }
    )
    sampler = (
        ALWAYS_ON
        if config.sampling_ratio >= 1.0
        else ParentBased(TraceIdRatioBased(config.sampling_ratio))
    )
    provider = TracerProvider(resource=resource, sampler=sampler)
    provider.add_span_processor(build_processor(config))
    # Flush the batch on process exit so short-lived scripts don't lose spans.
    # (We never set the global provider, so OTel's own atexit isn't registered.)
    atexit.register(provider.shutdown)
    return provider
