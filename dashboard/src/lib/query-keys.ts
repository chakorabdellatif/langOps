// Centralized TanStack Query key factory. Every useQuery in features/
// must take its key from here so SSE-driven invalidation stays consistent.

export const queryKeys = {
  executions: {
    all: ["executions"] as const,
    list: (filters: Record<string, unknown>) =>
      ["executions", "list", filters] as const,
    detail: (id: string) => ["executions", "detail", id] as const,
    timeline: (id: string) => ["executions", "timeline", id] as const,
    state: (id: string) => ["executions", "state", id] as const,
    logs: (id: string) => ["executions", "logs", id] as const,
  },
  nodes: {
    detail: (id: string) => ["nodes", "detail", id] as const,
  },
  graphs: {
    all: ["graphs"] as const,
    topology: (id: string) => ["graphs", "topology", id] as const,
  },
  costs: {
    summary: (params: Record<string, unknown>) =>
      ["costs", "summary", params] as const,
  },
  metrics: {
    overview: (params: Record<string, unknown>) =>
      ["metrics", "overview", params] as const,
  },
};
