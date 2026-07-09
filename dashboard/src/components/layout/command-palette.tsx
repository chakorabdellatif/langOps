"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { useSearch } from "@/lib/api/hooks";
import type { SearchHit } from "@/lib/api/types";

const KIND_LABEL: Record<string, string> = {
  execution: "Executions",
  graph: "Graphs",
  node: "Nodes",
  tool: "Tools",
  log: "Logs",
  llm: "LLM responses",
};

/** Global ⌘K / Ctrl+K search palette. Deep-links each hit to its destination. */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { data, isFetching } = useSearch(q);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  if (!open) return null;

  const go = (hit: SearchHit) => {
    setOpen(false);
    if (hit.kind === "graph") {
      router.push("/executions");
    } else if (hit.execution_id) {
      router.push(`/executions/${hit.execution_id}`);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-24"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-lg border border-neutral-700 bg-neutral-950 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search executions, nodes, tools, logs, LLM responses…"
          className="w-full border-b border-neutral-800 bg-transparent px-4 py-3 text-sm outline-none"
        />
        <div className="max-h-96 overflow-y-auto p-2">
          {q.trim() === "" && (
            <p className="px-2 py-6 text-center text-xs text-neutral-600">
              Type to search. Press <kbd>Esc</kbd> to close.
            </p>
          )}
          {q.trim() !== "" && isFetching && !data && (
            <p className="px-2 py-6 text-center text-xs text-neutral-500">Searching…</p>
          )}
          {data && data.groups.length === 0 && q.trim() !== "" && (
            <p className="px-2 py-6 text-center text-xs text-neutral-500">No matches.</p>
          )}
          {data?.groups.map((group) => (
            <div key={group.kind} className="mb-2">
              <div className="px-2 py-1 text-[10px] uppercase tracking-wide text-neutral-500">
                {KIND_LABEL[group.kind] ?? group.kind} · {group.total}
              </div>
              {group.hits.map((hit, i) => (
                <button
                  key={`${group.kind}-${i}`}
                  onClick={() => go(hit)}
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-neutral-800"
                >
                  <span className="truncate text-neutral-200">{hit.label}</span>
                  {hit.detail && (
                    <span className="ml-auto shrink-0 text-[10px] text-neutral-600">
                      {hit.detail}
                    </span>
                  )}
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
