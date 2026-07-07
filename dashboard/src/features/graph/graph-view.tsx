"use client";

import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  Position,
  type Edge,
  type Node,
  type NodeProps,
} from "reactflow";
import "reactflow/dist/style.css";

import { EmptyState } from "@/components/data";
import { useGraphTopology } from "@/lib/api/hooks";
import type { GraphTopology, NodeSummary, TopologyEdge, TopologyNode } from "@/lib/api/types";

const STATUS_BG: Record<string, string> = {
  succeeded: "#064e3b",
  failed: "#7f1d1d",
  running: "#0c4a6e",
  interrupted: "#78350f",
};

const CATEGORY_META: Record<string, { label: string; glyph: string; color: string }> = {
  llm: { label: "LLM Agent", glyph: "◆", color: "#c084fc" },
  tool: { label: "Tool Node", glyph: "⚒", color: "#38bdf8" },
  utility: { label: "Utility", glyph: "⚙", color: "#94a3b8" },
  router: { label: "Router", glyph: "⇄", color: "#fbbf24" },
  conditional: { label: "Conditional", glyph: "◇", color: "#fbbf24" },
  checkpoint: { label: "Checkpoint", glyph: "⛃", color: "#34d399" },
  subgraph: { label: "Subgraph", glyph: "▦", color: "#f472b6" },
};

function categoryMeta(category?: string) {
  return (category && CATEGORY_META[category]) || CATEGORY_META.utility;
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function fmtCost(usd: number | null, status: string): string {
  if (status === "unknown" || usd == null) return "Unknown";
  return `$${usd.toFixed(usd < 0.01 ? 6 : 4)}`;
}

function fmtDuration(ms: number | null): string {
  if (ms == null) return "—";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(2)} s`;
}

// ── topology normalisation (accepts v1 strings/tuples and v2 objects) ──

interface NormalNode {
  id: string;
  category?: string;
}
interface NormalEdge {
  source: string;
  target: string;
  conditional: boolean;
}

function normalize(topology: GraphTopology): { nodes: NormalNode[]; edges: NormalEdge[] } {
  const nodes = topology.nodes.map((n) =>
    typeof n === "string" ? { id: n } : { id: (n as TopologyNode).id, category: (n as TopologyNode).category },
  );
  const edges = topology.edges.map((e) =>
    Array.isArray(e)
      ? { source: e[0], target: e[1], conditional: false }
      : { source: (e as TopologyEdge).source, target: (e as TopologyEdge).target, conditional: Boolean((e as TopologyEdge).conditional) },
  );
  return { nodes, edges };
}

/** Left-to-right layered layout from the topology edges (no dagre dependency). */
function layout(nodes: string[], edges: [string, string][]): Map<string, number> {
  const depth = new Map<string, number>();
  nodes.forEach((n) => depth.set(n, 0));
  for (let i = 0; i < nodes.length; i++) {
    for (const [source, target] of edges) {
      const d = (depth.get(source) ?? 0) + 1;
      if (d > (depth.get(target) ?? 0)) depth.set(target, d);
    }
  }
  return depth;
}

// ── custom node with badges + hover tooltip ────────────────────────────

interface NodeData {
  name: string;
  category: string;
  node: NodeSummary | null;
}

function GraphNode({ data }: NodeProps<NodeData>) {
  const { name, category, node } = data;
  const meta = categoryMeta(category);
  const status = node?.status;
  const bg = status ? STATUS_BG[status] ?? "#1f2937" : "#111827";

  const badges: string[] = [];
  if (node?.duration_ms != null) badges.push(fmtDuration(node.duration_ms));
  if (node && node.total_tokens > 0) badges.push(`${fmtTokens(node.total_tokens)} tok`);
  if (node && (node.total_cost != null || node.cost_status === "priced"))
    badges.push(fmtCost(node.total_cost, node.cost_status));
  if (node && node.retry_count > 0) badges.push(`↻${node.retry_count}`);

  return (
    <div
      className="group relative"
      style={{
        background: bg,
        color: "#e5e7eb",
        border: node?.error ? "1px solid #ef4444" : "1px solid #374151",
        borderRadius: 8,
        width: 172,
        padding: 8,
        fontSize: 12,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: "#4b5563" }} />
      <div className="flex items-center justify-between">
        <span className="font-medium">{name}</span>
        <span title={meta.label} style={{ color: meta.color }}>
          {meta.glyph}
        </span>
      </div>
      <div className="mt-0.5 text-[10px] uppercase tracking-wide" style={{ color: meta.color }}>
        {meta.label}
      </div>
      {badges.length > 0 && (
        <div className="mt-1 text-[10px] opacity-80">{badges.join(" · ")}</div>
      )}
      {node && <NodeTooltip name={name} meta={meta} node={node} />}
      <Handle type="source" position={Position.Right} style={{ background: "#4b5563" }} />
    </div>
  );
}

function NodeTooltip({
  name,
  meta,
  node,
}: {
  name: string;
  meta: { label: string };
  node: NodeSummary;
}) {
  const failed = node.status === "failed";
  const changes = node.state_changes;
  return (
    <div className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 hidden w-64 -translate-x-1/2 rounded-md border border-neutral-700 bg-neutral-950 p-3 text-left text-[11px] shadow-xl group-hover:block">
      <div className="mb-1 font-semibold text-neutral-100">{name}</div>
      <Row k="Status" v={node.status} />
      <Row k="Node Type" v={meta.label} />
      <Row k="Duration" v={fmtDuration(node.duration_ms)} />
      {node.category === "llm" ? (
        <>
          <Row k="Input Tokens" v={String(node.input_tokens)} />
          <Row k="Output Tokens" v={String(node.output_tokens)} />
          <Row k="Total Tokens" v={String(node.total_tokens)} />
          <Row k="Cost" v={fmtCost(node.total_cost, node.cost_status)} />
          {node.models.length > 0 && <Row k="LLM" v={node.models.join(", ")} />}
        </>
      ) : (
        <>
          <Row k="Tokens" v="—" />
          <Row k="Cost" v="—" />
        </>
      )}
      {node.tool_names.length > 0 && <Row k="Tools" v={node.tool_names.join(", ")} />}
      {node.retry_count > 0 && <Row k="Retry Count" v={String(node.retry_count)} />}
      {failed && node.error && (
        <div className="mt-1 border-t border-neutral-800 pt-1 text-rose-300">
          <div>{String(node.error.type ?? "Exception")}</div>
          {node.error.message != null && (
            <div className="text-neutral-400">{String(node.error.message)}</div>
          )}
        </div>
      )}
      {(changes.added.length > 0 || changes.modified.length > 0 || changes.removed.length > 0) && (
        <div className="mt-1 border-t border-neutral-800 pt-1">
          <div className="mb-0.5 text-neutral-500">State Changes</div>
          {changes.added.map((k) => (
            <div key={`a-${k}`} className="text-emerald-400">+ {k}</div>
          ))}
          {changes.modified.map((k) => (
            <div key={`m-${k}`} className="text-amber-400">~ {k}</div>
          ))}
          {changes.removed.map((k) => (
            <div key={`r-${k}`} className="text-rose-400">− {k}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-neutral-500">{k}</span>
      <span className="truncate text-neutral-200">{v}</span>
    </div>
  );
}

const nodeTypes = { langops: GraphNode };

export function GraphView({
  graphId,
  nodeStatus,
  onSelectNode,
}: {
  graphId: string | null;
  nodeStatus: Record<string, NodeSummary>;
  onSelectNode?: (nodeId: string) => void;
}) {
  const { data: topology, isLoading } = useGraphTopology(graphId);

  const { nodes, edges } = useMemo(() => {
    if (!topology) return { nodes: [] as Node[], edges: [] as Edge[] };
    const norm = normalize(topology);
    const nodeIds = norm.nodes.map((n) => n.id);
    const edgePairs = norm.edges.map((e) => [e.source, e.target] as [string, string]);
    const depth = layout(nodeIds, edgePairs);
    const rowByDepth = new Map<number, number>();

    const flowNodes: Node[] = norm.nodes.map((n) => {
      const d = depth.get(n.id) ?? 0;
      const row = rowByDepth.get(d) ?? 0;
      rowByDepth.set(d, row + 1);
      const node = nodeStatus[n.id] ?? null;
      // Runtime category (from the executed node) wins over the static topology hint.
      const category = node?.category ?? n.category ?? "utility";
      return {
        id: n.id,
        type: "langops",
        position: { x: d * 230, y: row * 108 },
        data: { name: n.id, category, node } satisfies NodeData,
      };
    });

    const flowEdges: Edge[] = norm.edges.map((e, i) => ({
      id: `e${i}`,
      source: e.source,
      target: e.target,
      animated: nodeStatus[e.target]?.status === "running",
      label: e.conditional ? "conditional" : undefined,
      labelStyle: { fill: "#fbbf24", fontSize: 9 },
      style: {
        stroke: e.conditional ? "#a16207" : "#4b5563",
        strokeDasharray: e.conditional ? "4 3" : undefined,
      },
    }));
    return { nodes: flowNodes, edges: flowEdges };
  }, [topology, nodeStatus]);

  if (!graphId) return <EmptyState>This execution has no associated graph topology.</EmptyState>;
  if (isLoading) return <p className="text-sm text-neutral-500">Loading graph…</p>;
  if (!topology) return <EmptyState>Topology unavailable.</EmptyState>;

  return (
    <div className="h-[520px] rounded-lg border border-neutral-800 bg-neutral-950">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onSelectNode?.(node.id)}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1f2937" gap={16} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
