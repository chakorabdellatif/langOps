"""Deterministic execution comparison — pure, no I/O, never an LLM (v0.2).

Given two executions' key facts, computes four sections — execution/topology
changes, performance deltas, LLM changes — and derives plain-language,
threshold-driven insights. Everything is a pure function of the inputs, so it
is fully snapshot-testable and produces identical output for identical runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

# ── inputs (built by the application layer from repos) ─────────────────


@dataclass(frozen=True)
class NodeStat:
    name: str
    sequence: int
    retry_count: int
    duration_ms: int | None
    category: str


@dataclass(frozen=True)
class LlmStat:
    model: str | None
    temperature: float | None
    prompt_chars: int
    response_chars: int


@dataclass(frozen=True)
class ComparisonInput:
    status: str
    duration_ms: int | None
    total_tokens: int
    total_cost: Decimal | None  # None when any call is unpriced (incomparable)
    topology_hash: str | None
    context_size_bytes: int  # peak state size across the run
    nodes: list[NodeStat]
    llm_calls: list[LlmStat]
    tool_call_count: int


# ── outputs ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MetricDelta:
    a: float | None
    b: float | None
    delta: float | None
    delta_pct: float | None
    comparable: bool


@dataclass(frozen=True)
class ExecutionChanges:
    nodes_added: list[str]
    nodes_removed: list[str]
    order_changed: bool
    retries_added: list[str]
    retries_removed: list[str]
    topology_changed: bool


@dataclass(frozen=True)
class PerformanceChanges:
    duration: MetricDelta
    cost: MetricDelta
    total_tokens: MetricDelta
    context_size: MetricDelta
    node_latency: list[dict[str, object]]  # {node, a, b, delta_pct}


@dataclass(frozen=True)
class LlmChanges:
    model_changed: bool
    models_a: list[str]
    models_b: list[str]
    temperature_changed: bool
    prompt_changed: bool
    prompt_chars: MetricDelta
    response_chars: MetricDelta
    tool_calls: MetricDelta


@dataclass(frozen=True)
class Insight:
    text: str
    metric: str
    severity: str  # info | good | bad


@dataclass(frozen=True)
class ComparisonResult:
    execution_changes: ExecutionChanges
    performance: PerformanceChanges
    llm_changes: LlmChanges
    insights: list[Insight] = field(default_factory=list)


# ── thresholds (single source of truth for the insight rules) ──────────


class Thresholds:
    DURATION_PCT = 25.0
    COST_PCT = 15.0
    TOKENS_PCT = 20.0
    CONTEXT_PCT = 50.0
    NODE_LATENCY_PCT = 40.0


def _delta(a: float | None, b: float | None) -> MetricDelta:
    if a is None or b is None:
        return MetricDelta(a=a, b=b, delta=None, delta_pct=None, comparable=False)
    delta = b - a
    pct = (delta / a * 100.0) if a != 0 else None
    return MetricDelta(a=a, b=b, delta=delta, delta_pct=pct, comparable=True)


def _f(value: float | int | Decimal | None) -> float | None:
    return None if value is None else float(value)


class ExecutionComparator:
    def compare(self, a: ComparisonInput, b: ComparisonInput) -> ComparisonResult:
        execution_changes = self._execution_changes(a, b)
        performance = self._performance(a, b)
        llm_changes = self._llm_changes(a, b)
        insights = self._insights(a, b, execution_changes, performance, llm_changes)
        return ComparisonResult(
            execution_changes=execution_changes,
            performance=performance,
            llm_changes=llm_changes,
            insights=insights,
        )

    def _execution_changes(self, a: ComparisonInput, b: ComparisonInput) -> ExecutionChanges:
        a_names = {n.name for n in a.nodes}
        b_names = {n.name for n in b.nodes}
        a_retries = {n.name for n in a.nodes if n.retry_count > 0}
        b_retries = {n.name for n in b.nodes if n.retry_count > 0}
        a_order = [n.name for n in sorted(a.nodes, key=lambda n: n.sequence)]
        b_order = [n.name for n in sorted(b.nodes, key=lambda n: n.sequence)]
        # Order change only counts among nodes both runs share.
        shared = a_names & b_names
        a_shared_order = [n for n in a_order if n in shared]
        b_shared_order = [n for n in b_order if n in shared]
        return ExecutionChanges(
            nodes_added=sorted(b_names - a_names),
            nodes_removed=sorted(a_names - b_names),
            order_changed=a_shared_order != b_shared_order,
            retries_added=sorted(b_retries - a_retries),
            retries_removed=sorted(a_retries - b_retries),
            topology_changed=(a.topology_hash or "") != (b.topology_hash or ""),
        )

    def _performance(self, a: ComparisonInput, b: ComparisonInput) -> PerformanceChanges:
        a_lat = {n.name: n.duration_ms for n in a.nodes}
        node_latency: list[dict[str, object]] = []
        for name in sorted(a_lat.keys() & {n.name for n in b.nodes}):
            b_lat = next(n.duration_ms for n in b.nodes if n.name == name)
            d = _delta(_f(a_lat[name]), _f(b_lat))
            node_latency.append({"node": name, "a": d.a, "b": d.b, "delta_pct": d.delta_pct})
        return PerformanceChanges(
            duration=_delta(_f(a.duration_ms), _f(b.duration_ms)),
            cost=_delta(_f(a.total_cost), _f(b.total_cost)),
            total_tokens=_delta(_f(a.total_tokens), _f(b.total_tokens)),
            context_size=_delta(_f(a.context_size_bytes), _f(b.context_size_bytes)),
            node_latency=node_latency,
        )

    def _llm_changes(self, a: ComparisonInput, b: ComparisonInput) -> LlmChanges:
        models_a = sorted({c.model for c in a.llm_calls if c.model})
        models_b = sorted({c.model for c in b.llm_calls if c.model})
        temps_a = {c.temperature for c in a.llm_calls if c.temperature is not None}
        temps_b = {c.temperature for c in b.llm_calls if c.temperature is not None}
        prompt_a = sum(c.prompt_chars for c in a.llm_calls)
        prompt_b = sum(c.prompt_chars for c in b.llm_calls)
        resp_a = sum(c.response_chars for c in a.llm_calls)
        resp_b = sum(c.response_chars for c in b.llm_calls)
        return LlmChanges(
            model_changed=models_a != models_b,
            models_a=models_a,
            models_b=models_b,
            temperature_changed=temps_a != temps_b,
            prompt_changed=prompt_a != prompt_b,
            prompt_chars=_delta(float(prompt_a), float(prompt_b)),
            response_chars=_delta(float(resp_a), float(resp_b)),
            tool_calls=_delta(float(a.tool_call_count), float(b.tool_call_count)),
        )

    def _insights(
        self,
        a: ComparisonInput,
        b: ComparisonInput,
        changes: ExecutionChanges,
        perf: PerformanceChanges,
        llm: LlmChanges,
    ) -> list[Insight]:
        out: list[Insight] = []

        if changes.topology_changed:
            out.append(Insight("Graph topology changed.", "topology", "info"))
        for name in changes.nodes_added:
            out.append(Insight(f"New node executed: {name}.", "nodes", "info"))
        for name in changes.nodes_removed:
            out.append(Insight(f"Node no longer executed: {name}.", "nodes", "info"))
        if changes.order_changed:
            out.append(Insight("Execution order changed.", "order", "info"))
        if changes.retries_added:
            n = len(changes.retries_added)
            out.append(Insight(f"{n} retry{'s' if n > 1 else ''} occurred.", "retries", "bad"))
        if changes.retries_removed:
            out.append(Insight(f"{len(changes.retries_removed)} retry removed.", "retries", "good"))

        out += self._delta_insight(perf.duration, "Execution", "duration", "s", scale=1000.0)
        out += self._delta_insight(perf.cost, "Cost", "cost", "", pct_threshold=Thresholds.COST_PCT)
        out += self._delta_insight(
            perf.total_tokens, "LLM token usage", "tokens", "", pct_threshold=Thresholds.TOKENS_PCT
        )
        out += self._delta_insight(
            perf.context_size,
            "Context size",
            "context",
            "",
            pct_threshold=Thresholds.CONTEXT_PCT,
        )

        # Per-node latency spikes.
        for row in perf.node_latency:
            pct = row["delta_pct"]
            if isinstance(pct, float) and abs(pct) >= Thresholds.NODE_LATENCY_PCT:
                verb = "increased" if pct > 0 else "decreased"
                sev = "bad" if pct > 0 else "good"
                out.append(
                    Insight(
                        f"{row['node']} node latency {verb} by {abs(pct):.0f}%.",
                        "node_latency",
                        sev,
                    )
                )

        if llm.model_changed:
            out.append(
                Insight(
                    f"Model changed: {', '.join(llm.models_a) or '—'} → "
                    f"{', '.join(llm.models_b) or '—'}.",
                    "model",
                    "info",
                )
            )
        if llm.temperature_changed:
            out.append(Insight("Temperature changed.", "temperature", "info"))
        if llm.tool_calls.comparable and llm.tool_calls.delta not in (None, 0.0):
            out.append(
                Insight(
                    f"Tool calls changed from {int(a.tool_call_count)} → {int(b.tool_call_count)}.",
                    "tool_calls",
                    "info",
                )
            )
        return out

    def _delta_insight(
        self,
        d: MetricDelta,
        label: str,
        metric: str,
        unit: str,
        *,
        pct_threshold: float = Thresholds.DURATION_PCT,
        scale: float = 1.0,
    ) -> list[Insight]:
        if not d.comparable or d.delta_pct is None or abs(d.delta_pct) < pct_threshold:
            return []
        verb = "increased" if d.delta_pct > 0 else "decreased"
        # Cost/context/tokens: lower is better; here bad == went up.
        sev = "bad" if d.delta_pct > 0 else "good"
        amount = f" ({abs(d.delta) / scale:.1f}s)" if unit == "s" and d.delta is not None else ""
        return [Insight(f"{label} {verb} by {abs(d.delta_pct):.0f}%{amount}.", metric, sev)]
