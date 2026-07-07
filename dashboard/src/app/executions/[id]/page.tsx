"use client";

import { useState } from "react";
import { useParams } from "next/navigation";

import { Card, Cost, Duration, EmptyState, JsonViewer, StatusBadge, Tokens } from "@/components/data";
import { GraphView } from "@/features/graph/graph-view";
import { StateView } from "@/features/state/state-view";
import { TimelineView } from "@/features/timeline/timeline-view";
import {
  useExecution,
  useExecutionLlmCalls,
  useExecutionLogs,
  useExecutionToolCalls,
} from "@/lib/api/hooks";
import type { NodeSummary } from "@/lib/api/types";

const TABS = ["Overview", "Graph", "Timeline", "State", "LLM Calls", "Tool Calls", "Logs"] as const;
type Tab = (typeof TABS)[number];

export default function ExecutionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<Tab>("Overview");
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

      {tab === "Overview" && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Input">
            <JsonViewer value={data.input} />
          </Card>
          <Card title="Output">
            <JsonViewer value={data.output} />
          </Card>
          {ex.status === "failed" && data.error && (
            <div className="md:col-span-2">
              <Card title="Error">
                <JsonViewer value={data.error} />
              </Card>
            </div>
          )}
        </div>
      )}
      {tab === "Graph" && <GraphView graphId={ex.graph_id} nodeStatus={nodeStatus} />}
      {tab === "Timeline" && (
        <Card>
          <TimelineView executionId={id} nodes={data.nodes} />
        </Card>
      )}
      {tab === "State" && <StateView executionId={id} />}
      {tab === "LLM Calls" && <LlmCallsTab executionId={id} />}
      {tab === "Tool Calls" && <ToolCallsTab executionId={id} />}
      {tab === "Logs" && <LogsTab executionId={id} />}
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

function LlmCallsTab({ executionId }: { executionId: string }) {
  const { data, isLoading } = useExecutionLlmCalls(executionId);
  if (isLoading) return <p className="text-sm text-neutral-500">Loading…</p>;
  if (!data || data.length === 0) return <EmptyState>No LLM calls.</EmptyState>;
  return (
    <div className="space-y-4">
      {data.map((call) => (
        <Card key={call.id} title={`${call.provider ?? "?"} · ${call.model ?? "unknown model"}`}>
          <div className="mb-3 flex flex-wrap gap-4 text-xs text-neutral-400">
            <span>
              in <Tokens n={call.input_tokens} /> / out <Tokens n={call.output_tokens} />
            </span>
            <span>
              cost <Cost usd={call.total_cost} status={call.cost_status} />
            </span>
            <span>
              <Duration ms={call.latency_ms} />
            </span>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <div className="mb-1 text-xs uppercase text-neutral-500">Messages</div>
              <JsonViewer value={call.messages} />
            </div>
            <div>
              <div className="mb-1 text-xs uppercase text-neutral-500">Response</div>
              <JsonViewer value={call.response} />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

function ToolCallsTab({ executionId }: { executionId: string }) {
  const { data, isLoading } = useExecutionToolCalls(executionId);
  if (isLoading) return <p className="text-sm text-neutral-500">Loading…</p>;
  if (!data || data.length === 0) return <EmptyState>No tool calls.</EmptyState>;
  return (
    <div className="space-y-4">
      {data.map((call) => (
        <Card key={call.id} title={`Tool · ${call.tool_name}`}>
          <div className="mb-3 flex items-center gap-3 text-xs text-neutral-400">
            <StatusBadge status={call.status} />
            <Duration ms={call.duration_ms} />
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <div className="mb-1 text-xs uppercase text-neutral-500">Input</div>
              <JsonViewer value={call.input} />
            </div>
            <div>
              <div className="mb-1 text-xs uppercase text-neutral-500">Output</div>
              <JsonViewer value={call.output} />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
