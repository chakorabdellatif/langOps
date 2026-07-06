"use client";

import { useMemo } from "react";
import ReactFlow, { Background, Controls, type Edge, type Node } from "reactflow";
import "reactflow/dist/style.css";

import { EmptyState } from "@/components/data";
import { useGraphTopology } from "@/lib/api/hooks";
import type { NodeSummary } from "@/lib/api/types";

const STATUS_BG: Record<string, string> = {
  succeeded: "#064e3b",
  failed: "#7f1d1d",
  running: "#0c4a6e",
  interrupted: "#78350f",
};

/** Left-to-right layered layout from the topology edges (no dagre dependency). */
function layout(nodes: string[], edges: [string, string][]): Map<string, number> {
  const depth = new Map<string, number>();
  nodes.forEach((n) => depth.set(n, 0));
  // Relax depths a few times — DAGs converge quickly.
  for (let i = 0; i < nodes.length; i++) {
    for (const [source, target] of edges) {
      const d = (depth.get(source) ?? 0) + 1;
      if (d > (depth.get(target) ?? 0)) depth.set(target, d);
    }
  }
  return depth;
}

export function GraphView({
  graphId,
  nodeStatus,
}: {
  graphId: string | null;
  nodeStatus: Record<string, NodeSummary>;
}) {
  const { data: topology, isLoading } = useGraphTopology(graphId);

  const { nodes, edges } = useMemo(() => {
    if (!topology) return { nodes: [] as Node[], edges: [] as Edge[] };
    const depth = layout(topology.nodes, topology.edges);
    const rowByDepth = new Map<number, number>();
    const flowNodes: Node[] = topology.nodes.map((name) => {
      const d = depth.get(name) ?? 0;
      const row = rowByDepth.get(d) ?? 0;
      rowByDepth.set(d, row + 1);
      const status = nodeStatus[name]?.status;
      return {
        id: name,
        position: { x: d * 200, y: row * 90 },
        data: { label: name },
        style: {
          background: status ? STATUS_BG[status] ?? "#1f2937" : "#111827",
          color: "#e5e7eb",
          border: "1px solid #374151",
          borderRadius: 8,
          fontSize: 12,
          width: 150,
        },
      };
    });
    const flowEdges: Edge[] = topology.edges.map(([source, target], i) => ({
      id: `e${i}`,
      source,
      target,
      animated: nodeStatus[target]?.status === "running",
      style: { stroke: "#4b5563" },
    }));
    return { nodes: flowNodes, edges: flowEdges };
  }, [topology, nodeStatus]);

  if (!graphId) return <EmptyState>This execution has no associated graph topology.</EmptyState>;
  if (isLoading) return <p className="text-sm text-neutral-500">Loading graph…</p>;
  if (!topology) return <EmptyState>Topology unavailable.</EmptyState>;

  return (
    <div className="h-[480px] rounded-lg border border-neutral-800 bg-neutral-950">
      <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}>
        <Background color="#1f2937" gap={16} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
