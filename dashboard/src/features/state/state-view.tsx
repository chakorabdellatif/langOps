"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, EmptyState, JsonViewer } from "@/components/data";
import { useExecutionState } from "@/lib/api/hooks";
import type { StateDiff } from "@/lib/api/types";

function DiffBlock({ diff }: { diff: StateDiff | null }) {
  if (!diff) return <p className="text-xs text-neutral-500">No diff.</p>;
  const added = Object.keys(diff.added);
  const modified = Object.keys(diff.modified);
  return (
    <div className="space-y-1 text-xs">
      {added.map((k) => (
        <div key={`a-${k}`} className="rounded bg-emerald-500/10 px-2 py-1 text-emerald-300">
          + {k}: {JSON.stringify(diff.added[k]).slice(0, 120)}
        </div>
      ))}
      {modified.map((k) => (
        <div key={`m-${k}`} className="rounded bg-amber-500/10 px-2 py-1 text-amber-300">
          ~ {k}: {JSON.stringify(diff.modified[k].old).slice(0, 50)} →{" "}
          {JSON.stringify(diff.modified[k].new).slice(0, 50)}
        </div>
      ))}
      {diff.removed.map((k) => (
        <div key={`r-${k}`} className="rounded bg-rose-500/10 px-2 py-1 text-rose-300">
          − {k}
        </div>
      ))}
      {added.length + modified.length + diff.removed.length === 0 && (
        <p className="text-neutral-500">No changes.</p>
      )}
    </div>
  );
}

export function StateView({ executionId }: { executionId: string }) {
  const { data, isLoading } = useExecutionState(executionId);

  if (isLoading) return <p className="text-sm text-neutral-500">Loading state…</p>;
  if (!data || data.steps.length === 0)
    return <EmptyState>No state snapshots captured for this execution.</EmptyState>;

  const growth = data.context_growth.map((g, i) => ({
    step: g.node_name ? `${i + 1}. ${g.node_name}` : String(i + 1),
    size_bytes: g.size_bytes,
    messages: g.message_count ?? 0,
  }));

  return (
    <div className="space-y-6">
      <Card title="Context growth">
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={growth}>
              <CartesianGrid stroke="#262626" />
              <XAxis dataKey="step" tick={{ fill: "#a3a3a3", fontSize: 11 }} />
              <YAxis tick={{ fill: "#a3a3a3", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#171717", border: "1px solid #404040" }} />
              <Line type="monotone" dataKey="size_bytes" stroke="#38bdf8" dot />
              <Line type="monotone" dataKey="messages" stroke="#34d399" dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="space-y-4">
        {data.steps.map((step, i) => (
          <Card key={i} title={`${i + 1}. ${step.node_name ?? "state"} (${step.kind})`}>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <div className="mb-1 text-xs uppercase text-neutral-500">Diff</div>
                <DiffBlock diff={step.diff} />
              </div>
              <div>
                <div className="mb-1 text-xs uppercase text-neutral-500">State</div>
                <JsonViewer value={step.state} />
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
