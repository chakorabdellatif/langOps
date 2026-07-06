// Wire types mirroring the backend Pydantic schemas.
// Production path: `npm run generate:api` regenerates these from the live
// OpenAPI schema into ./generated. Hand-written here so the app type-checks
// and builds without a running backend.

export interface ExecutionSummary {
  id: string;
  trace_id: string;
  graph_id: string | null;
  status: "running" | "succeeded" | "failed" | "interrupted";
  thread_id: string | null;
  checkpoint_id: string | null;
  resumed: boolean;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
  sdk_version: string | null;
}

export interface ExecutionList {
  items: ExecutionSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface NodeSummary {
  id: string;
  node_name: string;
  sequence: number;
  status: string;
  retry_count: number;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  error: Record<string, unknown> | null;
}

export interface ExecutionDetail {
  execution: ExecutionSummary;
  graph_name: string | null;
  parent_checkpoint_id: string | null;
  error: Record<string, unknown> | null;
  input: unknown;
  output: unknown;
  nodes: NodeSummary[];
}

export interface TimelineEntry {
  kind: "node" | "llm" | "tool";
  id: string;
  name: string;
  status: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
}

export interface LlmCall {
  id: string;
  node_execution_id: string | null;
  provider: string | null;
  model: string | null;
  messages: unknown;
  params: unknown;
  response: unknown;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  input_cost: number | null;
  output_cost: number | null;
  total_cost: number | null;
  cost_status: "priced" | "unknown";
  latency_ms: number | null;
  started_at: string | null;
  error: Record<string, unknown> | null;
}

export interface ToolCall {
  id: string;
  node_execution_id: string | null;
  tool_name: string;
  input: unknown;
  output: unknown;
  status: string;
  error: Record<string, unknown> | null;
  duration_ms: number | null;
  started_at: string | null;
}

export interface StateSnapshotView {
  id: string;
  node_execution_id: string | null;
  kind: string;
  state: unknown;
  diff: StateDiff | null;
  size_bytes: number;
  message_count: number | null;
  created_at: string | null;
}

export interface StateDiff {
  added: Record<string, unknown>;
  modified: Record<string, { old: unknown; new: unknown }>;
  removed: string[];
}

export interface LogEntry {
  id: string;
  node_execution_id: string | null;
  level: string;
  message: string;
  stack_trace: string | null;
  attributes: Record<string, unknown> | null;
  timestamp: string | null;
}

export interface NodeDetail {
  node: NodeSummary;
  llm_calls: LlmCall[];
  tool_calls: ToolCall[];
  state_snapshots: StateSnapshotView[];
  logs: LogEntry[];
}

export interface StateStep {
  node_execution_id: string | null;
  node_name: string | null;
  kind: string;
  state: unknown;
  diff: StateDiff | null;
  size_bytes: number;
  message_count: number | null;
  created_at: string | null;
}

export interface StateEvolution {
  steps: StateStep[];
  context_growth: { node_name: string | null; size_bytes: number; message_count: number | null }[];
}

export interface GraphSummary {
  id: string;
  name: string;
  topology_hash: string;
  created_at: string;
}

export interface GraphTopology {
  nodes: string[];
  edges: [string, string][];
}

export interface CostByModel {
  provider: string | null;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  total_cost: number;
  calls: number;
  unknown_calls: number;
}

export interface CostSummary {
  total_cost: number;
  total_tokens: number;
  by_model: CostByModel[];
  by_day: { day: string; total_cost: number }[];
}

export interface MetricsOverview {
  total_executions: number;
  succeeded: number;
  failed: number;
  running: number;
  failure_rate: number;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  latency_p99_ms: number | null;
}
