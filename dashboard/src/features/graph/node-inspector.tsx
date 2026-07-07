"use client";

import { Cost, Duration, JsonViewer, StatusBadge, Tokens } from "@/components/data";
import { useNode } from "@/lib/api/hooks";

/** Slide-over inspector for one node, fed by GET /api/v1/nodes/{id}. */
export function NodeInspector({ nodeId, onClose }: { nodeId: string; onClose: () => void }) {
  const { data, isLoading } = useNode(nodeId);

  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true">
      <button
        aria-label="Close inspector"
        onClick={onClose}
        className="flex-1 bg-black/40"
      />
      <aside className="h-full w-full max-w-md overflow-y-auto border-l border-neutral-800 bg-neutral-950 p-5 shadow-2xl">
        {isLoading && <p className="text-sm text-neutral-500">Loading node…</p>}
        {!isLoading && !data && <p className="text-sm text-neutral-500">Node not found.</p>}
        {data && (
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={data.node.status} />
                  <h2 className="font-mono text-base text-neutral-100">{data.node.node_name}</h2>
                </div>
                <div className="mt-1 text-xs uppercase tracking-wide text-neutral-500">
                  {data.node.category}
                </div>
              </div>
              <button onClick={onClose} className="text-neutral-500 hover:text-neutral-200">
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <Field label="Duration">
                <Duration ms={data.node.duration_ms} />
              </Field>
              <Field label="Retries">{data.node.retry_count}</Field>
              <Field label="Tokens">
                <Tokens n={data.node.total_tokens} />
              </Field>
              <Field label="Cost">
                <Cost usd={data.node.total_cost} status={data.node.cost_status} />
              </Field>
            </div>

            {data.node.error && (
              <Section title="Error">
                <JsonViewer value={data.node.error} />
              </Section>
            )}

            {data.llm_calls.length > 0 && (
              <Section title={`LLM Calls (${data.llm_calls.length})`}>
                <div className="space-y-3">
                  {data.llm_calls.map((call) => (
                    <div key={call.id} className="rounded border border-neutral-800 p-2">
                      <div className="mb-1 flex flex-wrap gap-3 text-xs text-neutral-400">
                        <span className="text-neutral-200">{call.model ?? "unknown model"}</span>
                        <span>
                          in <Tokens n={call.input_tokens} /> / out <Tokens n={call.output_tokens} />
                        </span>
                        <span>
                          <Cost usd={call.total_cost} status={call.cost_status} />
                        </span>
                      </div>
                      <JsonViewer value={call.response} />
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {data.tool_calls.length > 0 && (
              <Section title={`Tool Calls (${data.tool_calls.length})`}>
                <div className="space-y-3">
                  {data.tool_calls.map((call) => (
                    <div key={call.id} className="rounded border border-neutral-800 p-2">
                      <div className="mb-1 text-xs text-neutral-200">{call.tool_name}</div>
                      <JsonViewer value={call.output} />
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {data.state_snapshots.length > 0 && (
              <Section title="State">
                {data.state_snapshots.map((snap) => (
                  <div key={snap.id} className="mb-2">
                    <div className="mb-1 text-xs uppercase text-neutral-500">{snap.kind}</div>
                    <JsonViewer value={snap.state} />
                  </div>
                ))}
              </Section>
            )}

            {data.logs.length > 0 && (
              <Section title={`Logs (${data.logs.length})`}>
                <div className="space-y-1 font-mono text-xs">
                  {data.logs.map((log) => (
                    <div key={log.id} className="flex gap-2">
                      <span className="uppercase text-neutral-500">{log.level}</span>
                      <span className="text-neutral-300">{log.message}</span>
                    </div>
                  ))}
                </div>
              </Section>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="mt-0.5 text-neutral-200">{children}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-neutral-200">{title}</h3>
      {children}
    </div>
  );
}
