"use client";

import { useState } from "react";

import { Card, Duration, EmptyState, StatusBadge } from "@/components/data";
import { useComparison, useExecutions } from "@/lib/api/hooks";
import type { ExecutionDetail, ExecutionSummary, StateDiff } from "@/lib/api/types";

export default function ComparePage() {
  const { data: list } = useExecutions({ page_size: 50 });
  const [a, setA] = useState<string | null>(null);
  const [b, setB] = useState<string | null>(null);
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
