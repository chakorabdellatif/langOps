"use client";

import { Cost, EmptyState, Tokens } from "@/components/data";
import { useExecutionLlmCalls, useExecutionToolCalls } from "@/lib/api/hooks";
import type { NodeSummary } from "@/lib/api/types";

const KIND_COLOR: Record<string, string> = {
  node: "bg-sky-500/70",
  llm: "bg-violet-500/70",
  tool: "bg-emerald-500/70",
};

interface Span {
  key: string;
  kind: "node" | "llm" | "tool";
  label: string;
  extra?: React.ReactNode;
  start: number;
  duration: number;
  depth: number;
}

function ms(iso: string | null): number | null {
  return iso ? new Date(iso).getTime() : null;
}

/** Grouped waterfall: each node, with its LLM and tool spans nested beneath. */
export function TimelineView({
  executionId,
  nodes,
}: {
  executionId: string;
  nodes: NodeSummary[];
}) {
  const llm = useExecutionLlmCalls(executionId);
  const tool = useExecutionToolCalls(executionId);

  if (llm.isLoading || tool.isLoading)
    return <p className="text-sm text-neutral-500">Loading timeline…</p>;

  const llmByNode = groupByNode(llm.data ?? []);
  const toolByNode = groupByNode(tool.data ?? []);

  // Flatten into ordered spans: node, then its children, in sequence order.
  const spans: Span[] = [];
  for (const node of [...nodes].sort((a, b) => a.sequence - b.sequence)) {
    const start = ms(node.started_at);
    if (start != null) {
      spans.push({
        key: `n-${node.id}`,
        kind: "node",
        label: `${node.sequence}. ${node.node_name}`,
        extra: node.retry_count > 0 ? `↻${node.retry_count}` : node.error ? "⚠ error" : undefined,
        start,
        duration: node.duration_ms ?? 0,
        depth: 0,
      });
    }
    for (const call of llmByNode[node.id] ?? []) {
      const s = ms(call.started_at);
      if (s != null)
        spans.push({
          key: `l-${call.id}`,
          kind: "llm",
          label: call.model ?? "llm",
          extra: (
            <span className="flex items-center gap-2">
              <Tokens n={call.input_tokens + call.output_tokens} />
              <Cost usd={call.total_cost} status={call.cost_status} />
            </span>
          ),
          start: s,
          duration: call.latency_ms ?? 0,
          depth: 1,
        });
    }
    for (const call of toolByNode[node.id] ?? []) {
      const s = ms(call.started_at);
      if (s != null)
        spans.push({
          key: `t-${call.id}`,
          kind: "tool",
          label: call.tool_name,
          start: s,
          duration: call.duration_ms ?? 0,
          depth: 1,
        });
    }
  }

  if (spans.length === 0) return <EmptyState>No spans to show.</EmptyState>;

  const t0 = Math.min(...spans.map((s) => s.start));
  const t1 = Math.max(...spans.map((s) => s.start + s.duration));
  const window = Math.max(t1 - t0, 1);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4 text-xs text-neutral-500">
        <Legend color="bg-sky-500/70" label="node" />
        <Legend color="bg-violet-500/70" label="llm" />
        <Legend color="bg-emerald-500/70" label="tool" />
        <span className="ml-auto">total {(window / 1000).toFixed(2)} s</span>
      </div>

      <div className="space-y-1">
        {spans.map((s) => {
          const left = ((s.start - t0) / window) * 100;
          const width = Math.max((s.duration / window) * 100, 0.6);
          return (
            <div key={s.key} className="flex items-center gap-3 text-xs">
              <div
                className={`w-52 shrink-0 truncate ${
                  s.depth === 0 ? "font-medium text-neutral-200" : "pl-4 text-neutral-400"
                }`}
              >
                <span className="mr-2 uppercase text-neutral-600">{s.kind}</span>
                {s.label}
              </div>
              <div className="relative h-4 flex-1 rounded bg-neutral-900/80">
                <div
                  className={`absolute h-4 rounded ${KIND_COLOR[s.kind]}`}
                  style={{ left: `${left}%`, width: `${width}%` }}
                  title={`${s.duration} ms`}
                />
              </div>
              <div className="flex w-40 shrink-0 items-center justify-end gap-3 text-right text-neutral-500">
                {s.extra}
                <span className="w-14">{s.duration} ms</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function groupByNode<T extends { node_execution_id: string | null }>(
  items: T[],
): Record<string, T[]> {
  const out: Record<string, T[]> = {};
  for (const item of items) {
    if (item.node_execution_id) (out[item.node_execution_id] ??= []).push(item);
  }
  return out;
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`inline-block h-2.5 w-2.5 rounded-sm ${color}`} />
      {label}
    </span>
  );
}
