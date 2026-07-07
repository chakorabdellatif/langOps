"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Card, Cost, Duration, EmptyState, JsonViewer, StatusBadge, Tokens } from "@/components/data";
import { GraphView } from "@/features/graph/graph-view";
import { NodeInspector } from "@/features/graph/node-inspector";
import { StateView } from "@/features/state/state-view";
import { TimelineView } from "@/features/timeline/timeline-view";
import {
  useExecution,
  useExecutionLlmCalls,
  useExecutionToolCalls,
  useLogs,
} from "@/lib/api/hooks";
import type { NodeSummary } from "@/lib/api/types";

const TABS = ["Overview", "Graph", "Timeline", "State", "LLM Calls", "Tool Calls", "Logs"] as const;
type Tab = (typeof TABS)[number];

export default function ExecutionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<Tab>("Overview");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
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
          <LogCountBadges executionId={id} />
          <Link
            href={`/compare?a=${ex.id}`}
            className="ml-auto rounded border border-neutral-700 px-2.5 py-1 text-xs text-neutral-300 hover:bg-neutral-800"
          >
            Compare with…
          </Link>
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
      {tab === "Graph" && (
        <GraphView
          graphId={ex.graph_id}
          nodeStatus={nodeStatus}
          onSelectNode={(name) => setSelectedNodeId(nodeStatus[name]?.id ?? null)}
        />
      )}
      {tab === "Timeline" && (
        <Card>
          <TimelineView executionId={id} nodes={data.nodes} />
        </Card>
      )}
      {tab === "State" && <StateView executionId={id} />}
      {tab === "LLM Calls" && <LlmCallsTab executionId={id} />}
      {tab === "Tool Calls" && <ToolCallsTab executionId={id} />}
      {tab === "Logs" && <LogsTab executionId={id} />}

      {selectedNodeId && (
        <NodeInspector nodeId={selectedNodeId} onClose={() => setSelectedNodeId(null)} />
      )}
    </div>
  );
}

function LogCountBadges({ executionId }: { executionId: string }) {
  const errors = useLogs({ execution_id: executionId, level: "error", limit: 1 });
  const warnings = useLogs({ execution_id: executionId, level: "warning", limit: 1 });
  const errCount = errors.data?.total ?? 0;
  const warnCount = warnings.data?.total ?? 0;
  if (errCount === 0 && warnCount === 0) return null;
  return (
    <span className="flex items-center gap-1.5 text-xs">
      {errCount > 0 && (
        <span className="rounded bg-rose-500/15 px-2 py-0.5 text-rose-300">{errCount} err</span>
      )}
      {warnCount > 0 && (
        <span className="rounded bg-amber-500/15 px-2 py-0.5 text-amber-300">{warnCount} warn</span>
      )}
    </span>
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

const LEVEL_COLORS: Record<string, string> = {
  error: "text-rose-400",
  critical: "text-rose-400",
  warning: "text-amber-400",
  info: "text-sky-400",
  debug: "text-neutral-500",
};
const SOURCE_FILTERS = ["app", "sdk", "llm", "tool", "exception"] as const;

function LogsTab({ executionId }: { executionId: string }) {
  const [level, setLevel] = useState<string>("");
  const [source, setSource] = useState<string>("");
  const [q, setQ] = useState<string>("");
  const { data, isLoading } = useLogs({
    execution_id: executionId,
    level: level || undefined,
    source: source || undefined,
    q: q || undefined,
    limit: 500,
  });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search messages…"
          className="w-56 rounded border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-sm"
        />
        <Chip active={level === ""} onClick={() => setLevel("")}>All levels</Chip>
        <Chip active={level === "error"} onClick={() => setLevel("error")}>Errors</Chip>
        <Chip active={level === "warning"} onClick={() => setLevel("warning")}>Warnings</Chip>
        <span className="mx-1 text-neutral-700">|</span>
        <Chip active={source === ""} onClick={() => setSource("")}>All sources</Chip>
        {SOURCE_FILTERS.map((s) => (
          <Chip key={s} active={source === s} onClick={() => setSource(s)}>
            {s.toUpperCase()}
          </Chip>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-neutral-500">Loading…</p>
      ) : !data || data.items.length === 0 ? (
        <EmptyState>No logs match these filters.</EmptyState>
      ) : (
        <Card>
          <div className="space-y-1.5 font-mono text-xs">
            {data.items.map((log) => (
              <div key={log.id} className="flex items-start gap-3">
                <span className="w-36 shrink-0 text-neutral-600">
                  {log.timestamp?.slice(11, 23) ?? "—"}
                </span>
                <span className={`w-16 shrink-0 uppercase ${LEVEL_COLORS[log.level] ?? "text-neutral-400"}`}>
                  {log.level}
                </span>
                <span className="w-14 shrink-0 text-neutral-600">{log.source}</span>
                <span className="flex-1 text-neutral-300">
                  {log.message}
                  {log.stack_trace && (
                    <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-neutral-900/70 p-2 text-[11px] text-rose-300">
                      {log.stack_trace}
                    </pre>
                  )}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-2 text-xs text-neutral-600">{data.total} log line(s)</div>
        </Card>
      )}
    </div>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded px-2.5 py-1 text-xs ring-1 ${
        active
          ? "bg-sky-500/15 text-sky-300 ring-sky-500/30"
          : "text-neutral-400 ring-neutral-700 hover:text-neutral-200"
      }`}
    >
      {children}
    </button>
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
