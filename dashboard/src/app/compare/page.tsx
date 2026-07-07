"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Card, Duration, EmptyState, StatusBadge } from "@/components/data";
import { useComparison, useExecutions } from "@/lib/api/hooks";
import type {
  ComparisonInsight,
  ComparisonResult,
  ExecutionDetail,
  ExecutionSummary,
  MetricDelta,
  StateDiff,
} from "@/lib/api/types";

export default function ComparePage() {
  return (
    <Suspense fallback={<p className="text-sm text-neutral-500">Loading…</p>}>
      <CompareView />
    </Suspense>
  );
}

function CompareView() {
  const params = useSearchParams();
  const { data: list } = useExecutions({ page_size: 50 });
  // Pre-fill side A from ?a=<id> (the "Compare with…" entry point).
  const [a, setA] = useState<string | null>(params.get("a"));
  const [b, setB] = useState<string | null>(params.get("b"));
  const { data: comparison, isLoading } = useComparison(a, b);

  const options = list?.items ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Compare executions</h1>

      <div className="grid grid-cols-2 gap-4">
        <Selector label="Execution A" value={a} onChange={setA} options={options} />
        <Selector label="Execution B" value={b} onChange={setB} options={options} />
      </div>

      {!a || !b ? (
        <EmptyState>Pick two executions to compare their metrics and final state.</EmptyState>
      ) : isLoading || !comparison ? (
        <p className="text-sm text-neutral-500">Loading comparison…</p>
      ) : (
        <>
          {comparison.result && <InsightsCard insights={comparison.result.insights} />}
          {comparison.result && <PerformanceCard result={comparison.result} />}
          {comparison.result && <ExecutionChangesCard result={comparison.result} />}
          {comparison.result && <LlmChangesCard result={comparison.result} />}

          <Card title="Metrics">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-neutral-500">
                <tr>
                  <th className="pb-2">Metric</th>
                  <th className="pb-2">A</th>
                  <th className="pb-2">B</th>
                  <th className="pb-2">Δ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800">
                <Row label="Status" a={<StatusBadge status={comparison.a.execution.status} />} b={<StatusBadge status={comparison.b.execution.status} />} />
                <NumRow label="Duration (ms)" a={comparison.a.execution.duration_ms} b={comparison.b.execution.duration_ms} />
                <NumRow label="Total tokens" a={tokens(comparison.a.execution)} b={tokens(comparison.b.execution)} />
                <NumRow label="Cost (USD)" a={comparison.a.execution.total_cost} b={comparison.b.execution.total_cost} digits={6} />
                <NumRow label="Nodes" a={comparison.a.nodes.length} b={comparison.b.nodes.length} />
                <NumRow label="Retries" a={retries(comparison.a)} b={retries(comparison.b)} />
              </tbody>
            </table>
          </Card>

          <div className="grid grid-cols-2 gap-4">
            <NodePathCard title="A · graph path" detail={comparison.a} />
            <NodePathCard title="B · graph path" detail={comparison.b} />
          </div>

          <Card title="Final state diff (A → B)">
            <FinalStateDiff diff={comparison.final_state_diff} />
          </Card>
        </>
      )}
    </div>
  );
}

function tokens(ex: ExecutionSummary): number {
  return ex.total_input_tokens + ex.total_output_tokens;
}
function retries(d: ExecutionDetail): number {
  return d.nodes.reduce((sum, n) => sum + n.retry_count, 0);
}

function Selector({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string | null;
  onChange: (v: string) => void;
  options: ExecutionSummary[];
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs uppercase text-neutral-500">{label}</span>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm"
      >
        <option value="">Select…</option>
        {options.map((ex) => (
          <option key={ex.id} value={ex.id}>
            {ex.id.slice(0, 8)} · {ex.status} · {ex.started_at?.slice(0, 19) ?? "—"}
          </option>
        ))}
      </select>
    </label>
  );
}

function Row({ label, a, b }: { label: string; a: React.ReactNode; b: React.ReactNode }) {
  return (
    <tr>
      <td className="py-2 text-neutral-400">{label}</td>
      <td className="py-2">{a}</td>
      <td className="py-2">{b}</td>
      <td className="py-2 text-neutral-600">—</td>
    </tr>
  );
}

function NumRow({
  label,
  a,
  b,
  digits = 0,
}: {
  label: string;
  a: number | null;
  b: number | null;
  digits?: number;
}) {
  const delta = a != null && b != null ? b - a : null;
  const fmt = (n: number | null) => (n == null ? "—" : n.toFixed(digits));
  const deltaColor = delta == null ? "text-neutral-600" : delta > 0 ? "text-rose-400" : delta < 0 ? "text-emerald-400" : "text-neutral-500";
  return (
    <tr>
      <td className="py-2 text-neutral-400">{label}</td>
      <td className="py-2">{fmt(a)}</td>
      <td className="py-2">{fmt(b)}</td>
      <td className={`py-2 ${deltaColor}`}>
        {delta == null ? "—" : `${delta > 0 ? "+" : ""}${delta.toFixed(digits)}`}
      </td>
    </tr>
  );
}

function NodePathCard({ title, detail }: { title: string; detail: ExecutionDetail }) {
  return (
    <Card title={title}>
      <ol className="space-y-1 text-sm">
        {detail.nodes.map((n) => (
          <li key={n.id} className="flex items-center justify-between">
            <span>
              {n.sequence}. {n.node_name}
            </span>
            <span className="flex items-center gap-2 text-xs text-neutral-500">
              <Duration ms={n.duration_ms} />
              {n.retry_count > 0 && <span className="text-amber-400">↻{n.retry_count}</span>}
              <StatusBadge status={n.status} />
            </span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

const SEVERITY: Record<string, string> = {
  good: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
  bad: "bg-rose-500/10 text-rose-300 ring-rose-500/30",
  info: "bg-sky-500/10 text-sky-300 ring-sky-500/30",
};

function InsightsCard({ insights }: { insights: ComparisonInsight[] }) {
  if (insights.length === 0)
    return (
      <Card title="Insights">
        <p className="text-sm text-emerald-400">No significant differences detected.</p>
      </Card>
    );
  return (
    <Card title="Insights">
      <ul className="space-y-2">
        {insights.map((i, idx) => (
          <li
            key={idx}
            className={`rounded px-3 py-2 text-sm ring-1 ${SEVERITY[i.severity] ?? SEVERITY.info}`}
          >
            {i.text}
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** ▲/▼ delta chip. Lower is better for latency/cost/tokens → down is green. */
function DeltaChip({ d, unit = "", lowerIsBetter = true }: { d: MetricDelta; unit?: string; lowerIsBetter?: boolean }) {
  if (!d.comparable || d.delta_pct == null)
    return <span className="text-neutral-500">incomparable</span>;
  const up = d.delta_pct > 0;
  const good = lowerIsBetter ? !up : up;
  const color = d.delta_pct === 0 ? "text-neutral-500" : good ? "text-emerald-400" : "text-rose-400";
  const arrow = d.delta_pct === 0 ? "" : up ? "▲" : "▼";
  return (
    <span className={color}>
      {arrow} {up ? "+" : ""}
      {d.delta_pct.toFixed(0)}%{unit}
    </span>
  );
}

function fmtNum(n: number | null, digits = 0): string {
  return n == null ? "—" : n.toFixed(digits);
}

function PerformanceCard({ result }: { result: ComparisonResult }) {
  const p = result.performance;
  const rows: { label: string; d: MetricDelta; digits?: number }[] = [
    { label: "Duration (ms)", d: p.duration },
    { label: "Cost (USD)", d: p.cost, digits: 6 },
    { label: "Total tokens", d: p.total_tokens },
    { label: "Context size (bytes)", d: p.context_size },
  ];
  return (
    <Card title="Performance">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-neutral-500">
          <tr>
            <th className="pb-2">Metric</th>
            <th className="pb-2">A</th>
            <th className="pb-2">B</th>
            <th className="pb-2">Δ</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-800">
          {rows.map((r) => (
            <tr key={r.label}>
              <td className="py-2 text-neutral-400">{r.label}</td>
              <td className="py-2">{fmtNum(r.d.a, r.digits)}</td>
              <td className="py-2">{fmtNum(r.d.b, r.digits)}</td>
              <td className="py-2">
                <DeltaChip d={r.d} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {p.node_latency.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 text-xs uppercase text-neutral-500">Per-node latency</div>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-neutral-800">
              {p.node_latency.map((n) => (
                <tr key={n.node}>
                  <td className="py-1.5 text-neutral-400">{n.node}</td>
                  <td className="py-1.5">{fmtNum(n.a)} ms</td>
                  <td className="py-1.5">{fmtNum(n.b)} ms</td>
                  <td className="py-1.5">
                    <DeltaChip
                      d={{ a: n.a, b: n.b, delta: null, delta_pct: n.delta_pct, comparable: n.delta_pct != null }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function ExecutionChangesCard({ result }: { result: ComparisonResult }) {
  const e = result.execution_changes;
  const unchanged =
    !e.topology_changed &&
    !e.order_changed &&
    e.nodes_added.length === 0 &&
    e.nodes_removed.length === 0 &&
    e.retries_added.length === 0 &&
    e.retries_removed.length === 0;
  return (
    <Card title="Execution changes">
      {unchanged ? (
        <p className="text-sm text-emerald-400">Same nodes, order, and topology.</p>
      ) : (
        <div className="space-y-1 text-sm">
          {e.topology_changed && <Line color="text-sky-300">Graph topology changed</Line>}
          {e.order_changed && <Line color="text-sky-300">Execution order changed</Line>}
          {e.nodes_added.map((n) => (
            <Line key={`na-${n}`} color="text-emerald-300">+ node {n}</Line>
          ))}
          {e.nodes_removed.map((n) => (
            <Line key={`nr-${n}`} color="text-rose-300">− node {n}</Line>
          ))}
          {e.retries_added.map((n) => (
            <Line key={`ra-${n}`} color="text-amber-300">↻ retry added on {n}</Line>
          ))}
          {e.retries_removed.map((n) => (
            <Line key={`rr-${n}`} color="text-emerald-300">retry removed on {n}</Line>
          ))}
        </div>
      )}
    </Card>
  );
}

function LlmChangesCard({ result }: { result: ComparisonResult }) {
  const l = result.llm_changes;
  return (
    <Card title="LLM changes">
      <div className="space-y-1 text-sm">
        <div className="flex justify-between">
          <span className="text-neutral-400">Model</span>
          <span className={l.model_changed ? "text-amber-300" : "text-neutral-300"}>
            {l.models_a.join(", ") || "—"} {l.model_changed ? "→" : "="} {l.models_b.join(", ") || "—"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-neutral-400">Temperature</span>
          <span className={l.temperature_changed ? "text-amber-300" : "text-neutral-300"}>
            {l.temperature_changed ? "changed" : "unchanged"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-neutral-400">Prompt size</span>
          <DeltaChip d={l.prompt_chars} />
        </div>
        <div className="flex justify-between">
          <span className="text-neutral-400">Response length</span>
          <DeltaChip d={l.response_chars} lowerIsBetter={false} />
        </div>
        <div className="flex justify-between">
          <span className="text-neutral-400">Tool calls</span>
          <span className="text-neutral-300">
            {fmtNum(l.tool_calls.a)} → {fmtNum(l.tool_calls.b)}
          </span>
        </div>
      </div>
    </Card>
  );
}

function Line({ color, children }: { color: string; children: React.ReactNode }) {
  return <div className={color}>{children}</div>;
}

function FinalStateDiff({ diff }: { diff: StateDiff | null }) {
  if (!diff) return <p className="text-sm text-neutral-500">Final outputs are not comparable objects.</p>;
  const added = Object.keys(diff.added);
  const modified = Object.keys(diff.modified);
  if (added.length + modified.length + diff.removed.length === 0)
    return <p className="text-sm text-emerald-400">Final states are identical.</p>;
  return (
    <div className="space-y-1 text-xs">
      {added.map((k) => (
        <div key={`a-${k}`} className="rounded bg-emerald-500/10 px-2 py-1 text-emerald-300">
          + {k}: {JSON.stringify(diff.added[k]).slice(0, 140)}
        </div>
      ))}
      {modified.map((k) => (
        <div key={`m-${k}`} className="rounded bg-amber-500/10 px-2 py-1 text-amber-300">
          ~ {k}: {JSON.stringify(diff.modified[k].old).slice(0, 60)} → {JSON.stringify(diff.modified[k].new).slice(0, 60)}
        </div>
      ))}
      {diff.removed.map((k) => (
        <div key={`r-${k}`} className="rounded bg-rose-500/10 px-2 py-1 text-rose-300">
          − {k}
        </div>
      ))}
    </div>
  );
}
