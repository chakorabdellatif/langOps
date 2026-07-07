"use client";

import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "@/lib/query-keys";
import { apiFetch } from "./client";
import type {
  CostSummary,
  ExecutionComparison,
  ExecutionDetail,
  ExecutionList,
  GraphSummary,
  GraphTopology,
  LlmCall,
  LogEntry,
  LogFilters,
  LogPage,
  MetricsOverview,
  NodeDetail,
  StateEvolution,
  TimelineEntry,
  ToolCall,
} from "./types";

export interface ExecutionFilters {
  status?: string;
  thread_id?: string;
  page?: number;
  page_size?: number;
}

function query(filters: object): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "" && value !== null) params.set(key, String(value));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

export function useExecutions(filters: ExecutionFilters = {}) {
  return useQuery({
    queryKey: queryKeys.executions.list(filters as Record<string, unknown>),
    queryFn: () => apiFetch<ExecutionList>(`/api/v1/executions${query(filters)}`),
    refetchInterval: 5000,
  });
}

export function useExecution(id: string) {
  return useQuery({
    queryKey: queryKeys.executions.detail(id),
    queryFn: () => apiFetch<ExecutionDetail>(`/api/v1/executions/${id}`),
  });
}

export function useTimeline(id: string) {
  return useQuery({
    queryKey: queryKeys.executions.timeline(id),
    queryFn: () => apiFetch<TimelineEntry[]>(`/api/v1/executions/${id}/timeline`),
  });
}

export function useExecutionState(id: string) {
  return useQuery({
    queryKey: queryKeys.executions.state(id),
    queryFn: () => apiFetch<StateEvolution>(`/api/v1/executions/${id}/state`),
  });
}

export function useExecutionLogs(id: string) {
  return useQuery({
    queryKey: queryKeys.executions.logs(id),
    queryFn: () => apiFetch<LogEntry[]>(`/api/v1/executions/${id}/logs`),
  });
}

export function useLogs(filters: LogFilters = {}) {
  return useQuery({
    queryKey: queryKeys.logs.search(filters as Record<string, unknown>),
    queryFn: () => apiFetch<LogPage>(`/api/v1/logs${query(filters)}`),
  });
}

export function useExecutionLlmCalls(id: string) {
  return useQuery({
    queryKey: [...queryKeys.executions.detail(id), "llm-calls"],
    queryFn: () => apiFetch<LlmCall[]>(`/api/v1/executions/${id}/llm-calls`),
  });
}

export function useExecutionToolCalls(id: string) {
  return useQuery({
    queryKey: [...queryKeys.executions.detail(id), "tool-calls"],
    queryFn: () => apiFetch<ToolCall[]>(`/api/v1/executions/${id}/tool-calls`),
  });
}

export function useNode(id: string | null) {
  return useQuery({
    queryKey: queryKeys.nodes.detail(id ?? ""),
    queryFn: () => apiFetch<NodeDetail>(`/api/v1/nodes/${id}`),
    enabled: Boolean(id),
  });
}

export function useGraphTopology(graphId: string | null) {
  return useQuery({
    queryKey: queryKeys.graphs.topology(graphId ?? ""),
    queryFn: () => apiFetch<GraphTopology>(`/api/v1/graphs/${graphId}/topology`),
    enabled: Boolean(graphId),
  });
}

export function useGraphs() {
  return useQuery({
    queryKey: queryKeys.graphs.all,
    queryFn: () => apiFetch<GraphSummary[]>("/api/v1/graphs"),
  });
}

export function useCostSummary() {
  return useQuery({
    queryKey: queryKeys.costs.summary({}),
    queryFn: () => apiFetch<CostSummary>("/api/v1/costs/summary"),
  });
}

export function useMetrics() {
  return useQuery({
    queryKey: queryKeys.metrics.overview({}),
    queryFn: () => apiFetch<MetricsOverview>("/api/v1/metrics/overview"),
    refetchInterval: 10000,
  });
}

export function useComparison(a: string | null, b: string | null) {
  return useQuery({
    queryKey: queryKeys.executions.compare(a ?? "", b ?? ""),
    queryFn: () =>
      apiFetch<ExecutionComparison>(`/api/v1/executions/compare?a=${a}&b=${b}`),
    enabled: Boolean(a && b),
  });
}
