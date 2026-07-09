"use client";

import Link from "next/link";

import { Cost, EmptyState, RelativeTime, Tokens } from "@/components/data";
import { useThreads } from "@/lib/api/hooks";

export default function ThreadsPage() {
  const { data, isLoading } = useThreads();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Threads</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Conversations grouped by thread — every execution that shares a{" "}
          <code>thread_id</code>, with cumulative cost across turns.
        </p>
      </div>

      {isLoading ? (
        <p className="text-sm text-neutral-500">Loading…</p>
      ) : !data || data.items.length === 0 ? (
        <EmptyState>No threads yet. Run a graph with a thread_id to see conversations.</EmptyState>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-neutral-800">
          <table className="w-full text-sm">
            <thead className="bg-neutral-900/60 text-left text-xs uppercase text-neutral-500">
              <tr>
                <th className="px-4 py-2">Thread</th>
                <th className="px-4 py-2">Runs</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Tokens</th>
                <th className="px-4 py-2">Cost</th>
                <th className="px-4 py-2">Last activity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {data.items.map((t) => (
                <tr key={t.thread_id} className="hover:bg-neutral-900/40">
                  <td className="px-4 py-2 font-mono">
                    <Link
                      href={`/threads/${encodeURIComponent(t.thread_id)}`}
                      className="text-sky-400 hover:underline"
                    >
                      {t.thread_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2">{t.run_count}</td>
                  <td className="px-4 py-2 text-xs">
                    {t.succeeded > 0 && <span className="text-emerald-400">{t.succeeded}✓ </span>}
                    {t.failed > 0 && <span className="text-rose-400">{t.failed}✗ </span>}
                    {t.running > 0 && <span className="text-sky-400">{t.running}⟳</span>}
                  </td>
                  <td className="px-4 py-2">
                    <Tokens n={t.total_tokens} />
                  </td>
                  <td className="px-4 py-2">
                    <Cost usd={t.total_cost} />
                  </td>
                  <td className="px-4 py-2 text-neutral-400">
                    <RelativeTime iso={t.last_at} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
