"""Capture-layer unit tests — pure, no OTel."""

import json

from langops.capture import diff, redaction, state


def test_to_jsonable_passes_primitives_and_containers() -> None:
    value = {"a": 1, "b": [1, "two", None], "c": {"d": True}}
    assert state.to_jsonable(value) == value


def test_to_jsonable_falls_back_to_repr_for_unknown() -> None:
    class Weird:
        def __repr__(self) -> str:
            return "<weird>"

    assert state.to_jsonable(Weird()) == "<weird>"


def test_serialize_caps_oversized_payloads() -> None:
    encoded, truncated, size = state.serialize({"big": "x" * 1000}, max_bytes=64)
    assert truncated is True
    assert size > 64
    assert json.loads(encoded) == {"langops.truncated": True}


def test_serialize_keeps_small_payloads() -> None:
    encoded, truncated, size = state.serialize({"ok": 1}, max_bytes=1024)
    assert truncated is False
    assert json.loads(encoded) == {"ok": 1}


def test_count_messages() -> None:
    assert state.count_messages({"messages": [1, 2, 3]}) == 3
    assert state.count_messages({"no_messages": True}) is None


def test_diff_matches_added_modified_removed() -> None:
    result = diff.diff({"a": 1, "b": 2}, {"b": 3, "c": 4})
    assert result == {"added": {"c": 4}, "modified": {"b": {"old": 2, "new": 3}}, "removed": ["a"]}


def test_redaction_applies_hook() -> None:
    assert redaction.apply({"secret": "x"}, lambda v: {"secret": "***"}) == {"secret": "***"}


def test_redaction_fails_closed() -> None:
    def boom(_: object) -> object:
        raise RuntimeError("hook error")

    # A failing hook must never leak the original payload.
    assert redaction.apply({"secret": "x"}, boom) == {"langops.redaction_error": True}
