"""The public surface stays tiny: instrument() and LangOpsConfig."""

import langops


def test_public_surface_exports_instrument_and_config() -> None:
    assert callable(langops.instrument)
    assert langops.LangOpsConfig is not None


def test_config_defaults_target_local_stack() -> None:
    config = langops.LangOpsConfig()
    assert config.endpoint == "http://localhost:4317"
    assert config.sampling_ratio == 1.0
    assert config.max_payload_bytes > 0


def test_build_processor_injects_api_key_header() -> None:
    from langops.config import LangOpsConfig
    from langops.export.processors import build_processor

    processor = build_processor(LangOpsConfig(api_key="s3cr3t"))
    exporter = processor.span_exporter  # type: ignore[attr-defined]
    headers = getattr(exporter, "_headers", ())
    flat = str(headers)
    assert "authorization" in flat.lower() and "s3cr3t" in flat
