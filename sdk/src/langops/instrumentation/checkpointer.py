"""Checkpointer wrapper — authoritative checkpoint lineage.

Composition, not subclassing: a thin proxy delegates every attribute to the
wrapped ``BaseCheckpointSaver`` and only observes ``put``/``aput``, where state
is persisted. Each put records the checkpoint id (and its parent) onto the
current run so the execution span carries authoritative lineage rather than
inferring it from the run config. Graphs without a checkpointer degrade
gracefully — the wrapper is simply never installed.
"""

from __future__ import annotations

from typing import Any

from langops.instrumentation.runtime import current_run


class InstrumentedCheckpointer:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        # Delegate everything we don't explicitly override.
        return getattr(self._inner, name)

    def _record(self, config: Any, checkpoint: Any) -> None:
        run = current_run.get()
        if run is None:
            return
        try:
            checkpoint_id = checkpoint.get("id") if isinstance(checkpoint, dict) else None
            configurable = (config or {}).get("configurable", {}) or {}
            parent = configurable.get("checkpoint_id")
            if checkpoint_id:
                if run.checkpoint_id and run.checkpoint_id != checkpoint_id:
                    run.parent_checkpoint_id = run.checkpoint_id
                elif parent:
                    run.parent_checkpoint_id = parent
                run.checkpoint_id = checkpoint_id
        except Exception:  # noqa: BLE001 — observation must never break persistence
            return

    def put(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        self._record(config, checkpoint)
        return self._inner.put(config, checkpoint, metadata, new_versions)

    async def aput(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        self._record(config, checkpoint)
        return await self._inner.aput(config, checkpoint, metadata, new_versions)
