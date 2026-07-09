"use client";

import { useParams } from "next/navigation";

import { Card, Cost, Duration, EmptyState, ExecutionLink, StatusBadge, Tokens } from "@/components/data";
import { useThread } from "@/lib/api/hooks";

export default function ThreadDetailPage() {
  const { threadId } = useParams<{ threadId: string }>();
  const decoded = decodeURIComponent(threadId);
  const { data, isLoading } = useThread(decoded);

  if (isLoading) return <p className="text-sm text-neutral-500">Loading…</p>;
  if (!data || data.runs.length === 0) return <EmptyState>Thread not found.</EmptyState>;

  const totalTokens = data.runs[data.runs.length - 1]?.cumulative_tokens ?? 0;
  const totalCost = data.runs[data.runs.length - 1]?.cumulative_cost ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-mono text-lg">{decoded}</h1>
        <div className="mt-2 flex gap-6 text-sm text-neutral-400">
          <span>{data.runs.length} runs</span>
          <span>
            cumulative <Tokens n={totalTokens} /> tokens
          </span>
          <span>
            cumulative <Cost usd={totalCost} />
          </span>
        </div>
      </div>

      <Card title="Conversation timeline">
        <ol className="space-y-2">
          {data.runs.map((run, i) => {
            const ex = run.execution;
            return (
              <li
                key={ex.id}
                className="flex flex-wrap items-center gap-3 border-b border-neutral-800 pb-2 text-sm last:border-0"
              >
                <span className="w-6 text-neutral-600">{i + 1}</span>
                <StatusBadge status={ex.status} />
                <ExecutionLink id={ex.id}>{ex.id.slice(0, 12)}</ExecutionLink>
                {ex.resumed && <span className="text-xs text-amber-400">resumed</span>}
                {ex.replay_of_execution_id && (
                  <span className="text-xs text-violet-300">replay</span>
                )}
                <span className="ml-auto flex items-center gap-4 text-xs text-neutral-500">
                  <Duration ms={ex.duration_ms} />
                  <span>
                    +<Tokens n={ex.total_input_tokens + ex.total_output_tokens} /> tok
                  </span>
                  <span>
                    Σ <Tokens n={run.cumulative_tokens} /> · <Cost usd={run.cumulative_cost} />
                  </span>
                </span>
              </li>
            );
          })}
        </ol>
      </Card>
    </div>
  );
}
