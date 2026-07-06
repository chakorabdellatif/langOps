"use client";

import { Card, Duration, Stat } from "@/components/data";
import { useMetrics } from "@/lib/api/hooks";

export default function MetricsPage() {
  const { data, isLoading } = useMetrics();

  if (isLoading || !data) return <p className="text-sm text-neutral-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Metrics</h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Total executions">{data.total_executions}</Stat>
        <Stat label="Succeeded">{data.succeeded}</Stat>
        <Stat label="Failed">{data.failed}</Stat>
        <Stat label="Failure rate">{(data.failure_rate * 100).toFixed(1)}%</Stat>
      </div>

      <Card title="Latency percentiles">
        <div className="grid grid-cols-3 gap-4">
          <Percentile label="p50">
            <Duration ms={data.latency_p50_ms} />
          </Percentile>
          <Percentile label="p95">
            <Duration ms={data.latency_p95_ms} />
          </Percentile>
          <Percentile label="p99">
            <Duration ms={data.latency_p99_ms} />
          </Percentile>
        </div>
      </Card>
    </div>
  );
}

function Percentile({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-neutral-800 p-4 text-center">
      <div className="text-xs uppercase text-neutral-500">{label}</div>
      <div className="mt-1 text-xl font-semibold">{children}</div>
    </div>
  );
}
