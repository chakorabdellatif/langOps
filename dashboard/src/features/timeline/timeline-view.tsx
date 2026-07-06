"use client";

import { EmptyState } from "@/components/data";
import { useTimeline } from "@/lib/api/hooks";

const KIND_COLOR: Record<string, string> = {
  node: "bg-sky-500/60",
  llm: "bg-violet-500/60",
  tool: "bg-emerald-500/60",
};

/** Gantt-style waterfall of node/LLM/tool spans by start offset + duration. */
export function TimelineView({ executionId }: { executionId: string }) {
  const { data, isLoading } = useTimeline(executionId);

  if (isLoading) return <p className="text-sm text-neutral-500">Loading timeline…</p>;
  if (!data || data.length === 0) return <EmptyState>No spans to show.</EmptyState>;

  const starts = data.map((e) => (e.started_at ? new Date(e.started_at).getTime() : 0));
  const t0 = Math.min(...starts.filter(Boolean));
  const span =
    Math.max(
      ...data.map((e, i) => (starts[i] || t0) - t0 + (e.duration_ms ?? 0)),
      1,
    ) || 1;

  return (
    <div className="space-y-1.5">
      {data.map((entry, i) => {
        const offset = ((starts[i] || t0) - t0) / span;
        const width = Math.max((entry.duration_ms ?? 0) / span, 0.01);
        return (
          <div key={entry.id} className="flex items-center gap-3 text-xs">
            <div className="w-40 shrink-0 truncate text-neutral-400">
              <span className="mr-2 uppercase text-neutral-600">{entry.kind}</span>
              {entry.name}
            </div>
            <div className="relative h-4 flex-1 rounded bg-neutral-900">
              <div
                className={`absolute h-4 rounded ${KIND_COLOR[entry.kind] ?? "bg-neutral-600"}`}
                style={{ left: `${offset * 100}%`, width: `${width * 100}%` }}
                title={`${entry.duration_ms ?? 0} ms`}
              />
            </div>
            <div className="w-16 shrink-0 text-right text-neutral-500">
              {entry.duration_ms ?? 0} ms
            </div>
          </div>
        );
      })}
    </div>
  );
}
