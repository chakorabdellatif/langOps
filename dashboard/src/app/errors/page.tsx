"use client";

import Link from "next/link";

import { Card, EmptyState, ExecutionLink, RelativeTime, Stat } from "@/components/data";
import { useErrorSummary } from "@/lib/api/hooks";

export default function ErrorsPage() {
  const { data, isLoading } = useErrorSummary();

  if (isLoading) return <p className="text-sm text-neutral-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Errors</h1>

      {!data || data.groups.length === 0 ? (
        <EmptyState>No failures recorded. 🎉</EmptyState>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            <Stat label="Total failures">{data.total}</Stat>
            <Stat label="Distinct types">
              {new Set(data.groups.map((g) => g.error_type)).size}
            </Stat>
            <Stat label="Affected nodes">
              {new Set(data.groups.map((g) => g.node_name)).size}
            </Stat>
          </div>

          {data.trend.length > 0 && (
            <Card title="Failures over time">
              <Sparkline points={data.trend.map((t) => t.count)} labels={data.trend.map((t) => t.day)} />
            </Card>
          )}

          <Card title="By exception type × node">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-neutral-500">
                <tr>
                  <th className="pb-2">Exception</th>
                  <th className="pb-2">Node</th>
                  <th className="pb-2">Count</th>
                  <th className="pb-2">Last seen</th>
                  <th className="pb-2">Sample</th>
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800">
                {data.groups.map((g, i) => (
                  <tr key={i} className="hover:bg-neutral-900/40">
                    <td className="py-2 font-medium text-rose-300">{g.error_type}</td>
                    <td className="py-2 text-neutral-300">{g.node_name}</td>
                    <td className="py-2 tabular-nums">{g.count}</td>
                    <td className="py-2 text-neutral-400">
                      <RelativeTime iso={g.last_seen} />
                    </td>
                    <td className="py-2 font-mono">
                      <ExecutionLink id={g.sample_execution_id}>
                        {g.sample_execution_id.slice(0, 8)}
                      </ExecutionLink>
                    </td>
                    <td className="py-2 text-right">
                      <Link
                        href={`/executions?error_type=${encodeURIComponent(g.error_type)}`}
                        className="text-xs text-sky-400 hover:underline"
                      >
                        view all →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}

/** Minimal inline SVG sparkline — no chart dependency needed for a trend line. */
function Sparkline({ points, labels }: { points: number[]; labels: string[] }) {
  if (points.length === 0) return null;
  const max = Math.max(...points, 1);
  const w = 600;
  const h = 60;
  const step = points.length > 1 ? w / (points.length - 1) : 0;
  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${i * step} ${h - (p / max) * (h - 6)}`)
    .join(" ");
  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="none" height={80}>
        <path d={path} fill="none" stroke="#f43f5e" strokeWidth={2} />
        {points.map((p, i) => (
          <circle key={i} cx={i * step} cy={h - (p / max) * (h - 6)} r={2.5} fill="#f43f5e">
            <title>{`${labels[i]}: ${p}`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}
