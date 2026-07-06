"use client";

import { Card, Cost, Duration, EmptyState, ExecutionLink, StatusBadge, Stat } from "@/components/data";
import { useExecutions, useMetrics } from "@/lib/api/hooks";

export default function OverviewPage() {
  const metrics = useMetrics();
  const executions = useExecutions({ page_size: 8 });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Overview</h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Executions">{metrics.data?.total_executions ?? "—"}</Stat>
        <Stat label="Failure rate">
          {metrics.data ? `${(metrics.data.failure_rate * 100).toFixed(0)}%` : "—"}
        </Stat>
        <Stat label="Running">{metrics.data?.running ?? "—"}</Stat>
        <Stat label="p95 latency">
          <Duration ms={metrics.data?.latency_p95_ms ?? null} />
        </Stat>
      </div>

      <Card title="Recent executions">
        {executions.isLoading && <p className="text-sm text-neutral-500">Loading…</p>}
        {executions.data && executions.data.items.length === 0 && (
          <EmptyState>
            No executions yet. Instrument a graph with <code>langops.instrument()</code> and run it.
          </EmptyState>
        )}
        {executions.data && executions.data.items.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-neutral-500">
              <tr>
                <th className="pb-2">Status</th>
                <th className="pb-2">Execution</th>
                <th className="pb-2">Duration</th>
                <th className="pb-2">Cost</th>
                <th className="pb-2">Started</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {executions.data.items.map((ex) => (
                <tr key={ex.id}>
                  <td className="py-2">
                    <StatusBadge status={ex.status} />
                  </td>
                  <td className="py-2">
                    <ExecutionLink id={ex.id}>{ex.id.slice(0, 8)}</ExecutionLink>
                  </td>
                  <td className="py-2">
                    <Duration ms={ex.duration_ms} />
                  </td>
                  <td className="py-2">
                    <Cost usd={ex.total_cost} />
                  </td>
                  <td className="py-2 text-neutral-400">
                    {ex.started_at ? new Date(ex.started_at).toLocaleTimeString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
