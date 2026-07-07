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

export type NodeCategory =
  | "llm"
  | "tool"
  | "utility"
  | "router"
  | "conditional"
  | "checkpoint"
  | "subgraph";

export interface NodeStateChanges {
  added: string[];
  modified: string[];
  removed: string[];
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
  // v0.2 graph-inspection fields.
  category: NodeCategory | string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  total_cost: number | null;
  cost_status: "priced" | "unknown";
  models: string[];
  tool_names: string[];
  state_changes: NodeStateChanges;
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
  execution_id: string;
  node_execution_id: string | null;
  level: string;
  source: string;
  logger: string | null;
  message: string;
  stack_trace: string | null;
  attributes: Record<string, unknown> | null;
  timestamp: string | null;
}

export interface LogPage {
  items: LogEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface LogFilters {
  execution_id?: string;
  node_execution_id?: string;
  level?: string;
  source?: string;
  q?: string;
  limit?: number;
  offset?: number;
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

export interface TopologyNode {
  id: string;
  category?: NodeCategory | string;
}

export interface TopologyEdge {
  source: string;
  target: string;
  conditional?: boolean;
}

// Topology payload accepts both v1 (bare strings / 2-tuples) and v2 (objects).
export interface GraphTopology {
  nodes: (string | TopologyNode)[];
  edges: ([string, string] | TopologyEdge)[];
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
  avg_latency_ms: number | null;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  latency_p99_ms: number | null;
}

export interface MetricDelta {
  a: number | null;
  b: number | null;
  delta: number | null;
  delta_pct: number | null;
  comparable: boolean;
}

export interface ExecutionChanges {
  nodes_added: string[];
  nodes_removed: string[];
  order_changed: boolean;
  retries_added: string[];
  retries_removed: string[];
  topology_changed: boolean;
}

export interface PerformanceChanges {
  duration: MetricDelta;
  cost: MetricDelta;
  total_tokens: MetricDelta;
  context_size: MetricDelta;
  node_latency: { node: string; a: number | null; b: number | null; delta_pct: number | null }[];
}

export interface LlmChanges {
  model_changed: boolean;
  models_a: string[];
  models_b: string[];
  temperature_changed: boolean;
  prompt_changed: boolean;
  prompt_chars: MetricDelta;
  response_chars: MetricDelta;
  tool_calls: MetricDelta;
}

export interface ComparisonInsight {
  text: string;
  metric: string;
  severity: "info" | "good" | "bad";
}

export interface ComparisonResult {
  execution_changes: ExecutionChanges;
  performance: PerformanceChanges;
  llm_changes: LlmChanges;
  insights: ComparisonInsight[];
}

export interface ExecutionComparison {
  a: ExecutionDetail;
  b: ExecutionDetail;
  final_state_diff: StateDiff | null;
  result: ComparisonResult | null;
}
