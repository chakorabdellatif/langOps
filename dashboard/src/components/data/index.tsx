"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";

const STATUS_COLORS: Record<string, string> = {
  succeeded: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  running: "bg-sky-500/15 text-sky-300 ring-sky-500/30",
  failed: "bg-rose-500/15 text-rose-300 ring-rose-500/30",
  interrupted: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
};

export function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] ?? "bg-neutral-700/40 text-neutral-300 ring-neutral-600";
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ring-1 ${cls}`}>
      {status}
    </span>
  );
}

export function Duration({ ms }: { ms: number | null }) {
  if (ms == null) return <span className="text-neutral-500">—</span>;
  if (ms < 1000) return <span>{ms} ms</span>;
  return <span>{(ms / 1000).toFixed(2)} s</span>;
}

export function Cost({ usd, status }: { usd: number | null; status?: string }) {
  if (status === "unknown" || usd == null)
    return <span className="text-amber-400" title="Model not in pricing catalog">Unknown</span>;
  return <span>${usd.toFixed(usd < 0.01 ? 6 : 4)}</span>;
}

export function Tokens({ n }: { n: number }) {
  if (n >= 1_000_000) return <span>{(n / 1_000_000).toFixed(2)}M</span>;
  if (n >= 1_000) return <span>{(n / 1_000).toFixed(1)}k</span>;
  return <span>{n}</span>;
}

export function RelativeTime({ iso }: { iso: string | null }) {
  if (!iso) return <span className="text-neutral-500">—</span>;
  return <span title={iso}>{new Date(iso).toLocaleString()}</span>;
}

export function JsonViewer({ value }: { value: unknown }) {
  const [collapsed, setCollapsed] = useState(false);
  const [copied, setCopied] = useState(false);
  if (value == null) return <p className="text-sm text-neutral-500">No data.</p>;
  const text = JSON.stringify(value, null, 2);

  const copy = () => {
    void navigator.clipboard?.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <div className="rounded ring-1 ring-neutral-800">
      <div className="flex items-center justify-between border-b border-neutral-800 bg-neutral-900/70 px-2 py-1 text-xs text-neutral-400">
        <button onClick={() => setCollapsed((c) => !c)} className="hover:text-neutral-200">
          {collapsed ? "▸ expand" : "▾ collapse"}
        </button>
        <button onClick={copy} className="hover:text-neutral-200">
          {copied ? "copied" : "copy"}
        </button>
      </div>
      {!collapsed && (
        <pre className="max-h-96 overflow-auto bg-neutral-900/70 p-3 text-xs text-neutral-300">
          {text}
        </pre>
      )}
    </div>
  );
}

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
      {title && <h2 className="mb-3 text-sm font-semibold text-neutral-200">{title}</h2>}
      {children}
    </section>
  );
}

export function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-neutral-100">{children}</div>
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-neutral-800 p-8 text-center text-sm text-neutral-500">
      {children}
    </div>
  );
}

export function ExecutionLink({ id, children }: { id: string; children: ReactNode }) {
  return (
    <Link href={`/executions/${id}`} className="text-sky-400 hover:text-sky-300 hover:underline">
      {children}
    </Link>
  );
}
