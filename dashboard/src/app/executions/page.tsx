"use client";

import { useState } from "react";

import { Card, Cost, Duration, EmptyState, ExecutionLink, StatusBadge, Tokens } from "@/components/data";
import { useExecutions } from "@/lib/api/hooks";

const STATUSES = ["", "running", "succeeded", "failed", "interrupted"];

export default function ExecutionsPage() {
  const [status, setStatus] = useState("");
  const [model, setModel] = useState("");
  const [hasRetries, setHasRetries] = useState(false);
  const [page, setPage] = useState(1);
  const { data, isLoading } = useExecutions({
    status,
    model: model || undefined,
    has_retries: hasRetries || undefined,
    page,
    page_size: 20,
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Executions</h1>
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="rounded border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-sm"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s === "" ? "All statuses" : s}
            </option>
          ))}
        </select>
        <input
          value={model}
          onChange={(e) => {
            setModel(e.target.value);
            setPage(1);
          }}
          placeholder="Filter by model…"
          className="w-40 rounded border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-sm"
        />
        <label className="flex items-center gap-2 text-sm text-neutral-300">
          <input
            type="checkbox"
            checked={hasRetries}
            onChange={(e) => {
              setHasRetries(e.target.checked);
              setPage(1);
            }}
          />
          has retries
        </label>
      </div>

      <Card>
        {isLoading && <p className="text-sm text-neutral-500">Loading…</p>}
        {data && data.items.length === 0 && <EmptyState>No executions match.</EmptyState>}
        {data && data.items.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-neutral-500">
              <tr>
                <th className="pb-2">Status</th>
                <th className="pb-2">Execution</th>
                <th className="pb-2">Thread</th>
                <th className="pb-2">Duration</th>
                <th className="pb-2">Tokens</th>
                <th className="pb-2">Cost</th>
                <th className="pb-2">Started</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {data.items.map((ex) => (
                <tr key={ex.id} className="hover:bg-neutral-900/40">
                  <td className="py-2">
                    <StatusBadge status={ex.status} />
                  </td>
                  <td className="py-2 font-mono">
                    <ExecutionLink id={ex.id}>{ex.id.slice(0, 8)}</ExecutionLink>
                    {ex.resumed && <span className="ml-2 text-xs text-amber-400">resumed</span>}
                  </td>
                  <td className="py-2 text-neutral-400">{ex.thread_id ?? "—"}</td>
                  <td className="py-2">
                    <Duration ms={ex.duration_ms} />
                  </td>
                  <td className="py-2">
                    <Tokens n={ex.total_input_tokens + ex.total_output_tokens} />
                  </td>
                  <td className="py-2">
                    <Cost usd={ex.total_cost} />
                  </td>
                  <td className="py-2 text-neutral-400">
                    {ex.started_at ? new Date(ex.started_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <div className="flex items-center justify-between text-sm text-neutral-400">
        <span>{data?.total ?? 0} total</span>
        <div className="flex items-center gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded border border-neutral-800 px-3 py-1 disabled:opacity-40"
          >
            Prev
          </button>
          <span>
            {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded border border-neutral-800 px-3 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
