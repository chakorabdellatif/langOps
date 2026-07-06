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
