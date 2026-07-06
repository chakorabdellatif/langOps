"use client";

import { Card, Cost, Duration, EmptyState, JsonViewer, StatusBadge, Tokens } from "@/components/data";
import { useNode } from "@/lib/api/hooks";

export function NodeInspector({ nodeId }: { nodeId: string | null }) {
  const { data, isLoading } = useNode(nodeId);

  if (!nodeId) return <EmptyState>Select a node to inspect its LLM and tool calls.</EmptyState>;
  if (isLoading || !data) return <p className="text-sm text-neutral-500">Loading node…</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 text-sm">
        <StatusBadge status={data.node.status} />
        <span className="font-medium">{data.node.node_name}</span>
        <span className="text-neutral-500">
          seq {data.node.sequence} · <Duration ms={data.node.duration_ms} />
          {data.node.retry_count > 0 && ` · ${data.node.retry_count} retries`}
        </span>
      </div>

      {data.llm_calls.map((call) => (
        <Card key={call.id} title={`LLM · ${call.model ?? "unknown model"}`}>
          <div className="mb-3 flex flex-wrap gap-4 text-xs text-neutral-400">
            <span>{call.provider}</span>
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

      {data.tool_calls.map((call) => (
        <Card key={call.id} title={`Tool · ${call.tool_name}`}>
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

      {data.llm_calls.length === 0 && data.tool_calls.length === 0 && (
        <EmptyState>This node made no LLM or tool calls.</EmptyState>
      )}
    </div>
  );
}
