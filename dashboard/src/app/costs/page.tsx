"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, Cost, EmptyState, Stat, Tokens } from "@/components/data";
import { useCostSummary } from "@/lib/api/hooks";

export default function CostsPage() {
  const { data, isLoading } = useCostSummary();

  if (isLoading) return <p className="text-sm text-neutral-500">Loading…</p>;
  if (!data || data.by_model.length === 0)
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">Costs</h1>
        <EmptyState>No LLM calls recorded yet.</EmptyState>
      </div>
    );

  const byModel = data.by_model.map((m) => ({
    model: m.model ?? "unknown",
    cost: m.total_cost,
    unknown: m.unknown_calls > 0,
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Costs</h1>

      <div className="grid grid-cols-2 gap-4">
        <Stat label="Total cost">
          <Cost usd={data.total_cost} />
        </Stat>
        <Stat label="Total tokens">
          <Tokens n={data.total_tokens} />
        </Stat>
      </div>

      <Card title="Cost by model">
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={byModel}>
              <CartesianGrid stroke="#262626" />
              <XAxis dataKey="model" tick={{ fill: "#a3a3a3", fontSize: 11 }} />
              <YAxis tick={{ fill: "#a3a3a3", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#171717", border: "1px solid #404040" }} />
              <Bar dataKey="cost">
                {byModel.map((m, i) => (
                  <Cell key={i} fill={m.unknown ? "#f59e0b" : "#38bdf8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card title="By model">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-neutral-500">
            <tr>
              <th className="pb-2">Provider</th>
              <th className="pb-2">Model</th>
              <th className="pb-2">Calls</th>
              <th className="pb-2">Tokens</th>
              <th className="pb-2">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800">
            {data.by_model.map((m, i) => (
              <tr key={i}>
                <td className="py-2 text-neutral-400">{m.provider ?? "—"}</td>
                <td className="py-2">{m.model ?? "unknown"}</td>
                <td className="py-2">{m.calls}</td>
                <td className="py-2">
                  <Tokens n={m.input_tokens + m.output_tokens} />
                </td>
                <td className="py-2">
                  <Cost usd={m.total_cost} status={m.unknown_calls > 0 ? "unknown" : "priced"} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {data.by_node.length > 0 && (
        <Card title="By node — which nodes burn the budget">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-neutral-500">
              <tr>
                <th className="pb-2">Node</th>
                <th className="pb-2">Calls</th>
                <th className="pb-2">Tokens</th>
                <th className="pb-2">Cost</th>
                <th className="pb-2">Share</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {data.by_node.map((n, i) => {
                const share = data.total_cost > 0 ? (n.total_cost / data.total_cost) * 100 : 0;
                return (
                  <tr key={i}>
                    <td className="py-2">{n.node_name}</td>
                    <td className="py-2">{n.calls}</td>
                    <td className="py-2">
                      <Tokens n={n.input_tokens + n.output_tokens} />
                    </td>
                    <td className="py-2">
                      <Cost usd={n.total_cost} status={n.unknown_calls > 0 ? "unknown" : "priced"} />
                    </td>
                    <td className="py-2 text-neutral-400">
                      {n.unknown_calls > 0 ? "—" : `${share.toFixed(0)}%`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
