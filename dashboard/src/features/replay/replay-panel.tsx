"use client";

import { useState } from "react";
import Link from "next/link";

import { Card } from "@/components/data";
import type { ExecutionDetail } from "@/lib/api/types";

/**
 * Replay panel. LangOps replays run in the developer's environment via the SDK
 * CLI (the dashboard cannot execute user code), so this surfaces a copyable
 * command plus replay lineage links.
 */
export function ReplayPanel({ detail }: { detail: ExecutionDetail }) {
  const id = detail.execution.id;
  const command =
    `python -m langops replay ${id} \\\n` +
    `  --app your_module:graph --api-url http://localhost:8000`;

  return (
    <Card title="Replay">
      <p className="mb-2 text-xs text-neutral-500">
        Re-run this execution locally with the SDK. Add <code>--model</code>,{" "}
        <code>--temperature</code>, or <code>--input file.json</code> to experiment, or{" "}
        <code>--stub-llm</code> for a deterministic, zero-token replay from the recording. The
        dashboard cannot run your code, so copy the command below.
      </p>
      <CopyBlock text={command} />

      {detail.replay_of_execution_id && (
        <div className="mt-3 text-sm">
          <span className="text-neutral-500">Replay of </span>
          <Link
            href={`/executions/${detail.replay_of_execution_id}`}
            className="text-sky-400 hover:underline"
          >
            {detail.replay_of_execution_id.slice(0, 12)}
          </Link>
          {isCached(detail.replay_overrides) && <CachedBadge />}
          <Link
            href={`/compare?a=${detail.replay_of_execution_id}&b=${id}`}
            className="ml-3 text-xs text-sky-400 hover:underline"
          >
            Compare with original
          </Link>
          {detail.replay_overrides && (
            <div className="mt-1 text-xs text-amber-300">
              overrides: {JSON.stringify(detail.replay_overrides)}
            </div>
          )}
        </div>
      )}

      {detail.replays.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-xs uppercase text-neutral-500">Replays of this execution</div>
          <ul className="space-y-1 text-sm">
            {detail.replays.map((r) => (
              <li key={r.id} className="flex items-center gap-3">
                <Link href={`/executions/${r.id}`} className="text-sky-400 hover:underline">
                  {r.id.slice(0, 12)}
                </Link>
                <span className="text-xs text-neutral-500">{r.status}</span>
                {r.overrides && (
                  <span className="text-xs text-amber-300">{JSON.stringify(r.overrides)}</span>
                )}
                <Link
                  href={`/compare?a=${id}&b=${r.id}`}
                  className="text-xs text-sky-400 hover:underline"
                >
                  compare
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function isCached(overrides: Record<string, unknown> | null): boolean {
  const stubbed = overrides?.stubbed as { llm?: boolean; tools?: string[] } | undefined;
  return Boolean(stubbed && (stubbed.llm || (stubbed.tools?.length ?? 0) > 0));
}

function CachedBadge() {
  return (
    <span
      className="ml-2 rounded bg-violet-500/15 px-2 py-0.5 text-xs text-violet-300 ring-1 ring-violet-500/30"
      title="Cached replay — LLM/tool outputs served from the recording (zero tokens)"
    >
      cached
    </span>
  );
}

function CopyBlock({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    void navigator.clipboard?.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };
  return (
    <div className="rounded ring-1 ring-neutral-800">
      <div className="flex items-center justify-between border-b border-neutral-800 bg-neutral-900/70 px-2 py-1 text-xs text-neutral-400">
        <span>SDK command</span>
        <button onClick={copy} className="hover:text-neutral-200">
          {copied ? "copied" : "copy"}
        </button>
      </div>
      <pre className="overflow-auto bg-neutral-900/70 p-3 text-xs text-neutral-300">{text}</pre>
    </div>
  );
}
