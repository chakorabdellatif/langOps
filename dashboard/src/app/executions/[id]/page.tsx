"use client";

import { useState } from "react";
import { useParams } from "next/navigation";

import { Card, Cost, Duration, EmptyState, JsonViewer, StatusBadge, Tokens } from "@/components/data";
import { GraphView } from "@/features/graph/graph-view";
import { NodeInspector } from "@/features/llm-calls/node-inspector";
import { StateView } from "@/features/state/state-view";
import { TimelineView } from "@/features/timeline/timeline-view";
import { useExecution, useExecutionLogs } from "@/lib/api/hooks";
import type { NodeSummary } from "@/lib/api/types";

const TABS = ["Graph", "Timeline", "State", "Nodes", "Logs"] as const;
type Tab = (typeof TABS)[number];

export default function ExecutionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<Tab>("Graph");
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const { data, isLoading } = useExecution(id);

  if (isLoading) return <p className="text-sm text-neutral-500">Loading…</p>;
  if (!data) return <EmptyState>Execution not found.</EmptyState>;

  const ex = data.execution;
  const nodeStatus: Record<string, NodeSummary> = Object.fromEntries(
    data.nodes.map((n) => [n.node_name, n]),
  );

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <StatusBadge status={ex.status} />
          <h1 className="font-mono text-lg">{ex.id.slice(0, 12)}</h1>
          {ex.resumed && <span className="text-xs text-amber-400">resumed from checkpoint</span>}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-4 text-sm md:grid-cols-5">
          <Meta label="Graph">{data.graph_name ?? "—"}</Meta>
          <Meta label="Duration">
            <Duration ms={ex.duration_ms} />
          </Meta>
          <Meta label="Tokens">
            <Tokens n={ex.total_input_tokens + ex.total_output_tokens} />
          </Meta>
          <Meta label="Cost">
            <Cost usd={ex.total_cost} />
          </Meta>
          <Meta label="Thread">{ex.thread_id ?? "—"}</Meta>
        </div>
      </div>

      <div className="flex gap-1 border-b border-neutral-800">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm ${
              tab === t
                ? "border-b-2 border-sky-400 text-neutral-100"
                : "text-neutral-400 hover:text-neutral-200"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Graph" && <GraphView graphId={ex.graph_id} nodeStatus={nodeStatus} />}
      {tab === "Timeline" && (
        <Card>
          <TimelineView executionId={id} />
        </Card>
      )}
      {tab === "State" && <StateView executionId={id} />}
      {tab === "Nodes" && (
        <div className="grid gap-4 md:grid-cols-[240px_1fr]">
          <Card title="Nodes">
            <ul className="space-y-1">
              {data.nodes.map((n) => (
                <li key={n.id}>
                  <button
                    onClick={() => setSelectedNode(n.id)}
                    className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm ${
                      selectedNode === n.id ? "bg-neutral-800" : "hover:bg-neutral-900"
                    }`}
                  >
                    <span>
                      {n.sequence}. {n.node_name}
                    </span>
                    <StatusBadge status={n.status} />
                  </button>
                </li>
              ))}
            </ul>
          </Card>
          <NodeInspector nodeId={selectedNode} />
        </div>
      )}
      {tab === "Logs" && <LogsTab executionId={id} />}

      {(ex.status === "failed" && data.error) && (
        <Card title="Error">
          <JsonViewer value={data.error} />
        </Card>
      )}
    </div>
  );
}

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="mt-0.5 text-neutral-200">{children}</div>
    </div>
  );
}

function LogsTab({ executionId }: { executionId: string }) {
  const { data, isLoading } = useExecutionLogs(executionId);
  if (isLoading) return <p className="text-sm text-neutral-500">Loading…</p>;
  if (!data || data.length === 0) return <EmptyState>No logs.</EmptyState>;
  return (
    <Card>
      <div className="space-y-1 font-mono text-xs">
        {data.map((log) => (
          <div key={log.id} className="flex gap-3">
            <span className="uppercase text-neutral-500">{log.level}</span>
            <span className="text-neutral-300">{log.message}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
