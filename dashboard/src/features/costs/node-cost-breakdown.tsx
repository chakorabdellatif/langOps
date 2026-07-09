"use client";

import { Card } from "@/components/data";
import type { NodeSummary } from "@/lib/api/types";

const BAR_COLORS = ["#38bdf8", "#c084fc", "#34d399", "#fbbf24", "#f472b6", "#60a5fa"];

/**
 * Per-node cost share for one execution. Rules (ADR-0002): a node with an
 * uncataloged model is "unknown", never rendered 0%; if any contributing node
 * is unknown, the whole bar falls back to token share (always known); nodes
 * that made no LLM call are omitted (they are "—", not 0%).
 */
export function NodeCostBreakdown({ nodes }: { nodes: NodeSummary[] }) {
  const llmNodes = nodes.filter((n) => n.total_tokens > 0 || n.category === "llm");
  if (llmNodes.length === 0) return null;

  const anyUnknown = llmNodes.some((n) => n.cost_status === "unknown");
  const byTokens = anyUnknown;

  const value = (n: NodeSummary) => (byTokens ? n.total_tokens : n.total_cost ?? 0);
  const total = llmNodes.reduce((sum, n) => sum + value(n), 0);
  const rows = [...llmNodes]
    .map((n) => ({ node: n, v: value(n), pct: total > 0 ? (value(n) / total) * 100 : 0 }))
    .sort((a, b) => b.v - a.v);

  return (
    <Card title={`Cost breakdown by node${byTokens ? " (by tokens)" : ""}`}>
      {byTokens && (
        <p className="mb-3 text-xs text-amber-400">
          Some nodes use uncataloged models (cost unknown), so shares are shown by token usage.
        </p>
      )}
      <div className="mb-3 flex h-3 overflow-hidden rounded">
        {rows.map((r, i) => (
          <div
            key={r.node.id}
            style={{ width: `${r.pct}%`, background: BAR_COLORS[i % BAR_COLORS.length] }}
            title={`${r.node.node_name}: ${r.pct.toFixed(0)}%`}
          />
        ))}
      </div>
      <ul className="space-y-1 text-sm">
        {rows.map((r, i) => (
          <li key={r.node.id} className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 rounded-sm"
              style={{ background: BAR_COLORS[i % BAR_COLORS.length] }}
            />
            <span className="text-neutral-300">{r.node.node_name}</span>
            {r.node.cost_status === "unknown" && (
              <span className="text-xs text-amber-400" title="Model not in pricing catalog">
                unknown
              </span>
            )}
            <span className="ml-auto tabular-nums text-neutral-400">{r.pct.toFixed(0)}%</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
