"use client";

import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "@/lib/query-keys";
import { apiFetch } from "./client";
import type {
  CostSummary,
  ExecutionDetail,
  ExecutionList,
  GraphSummary,
  GraphTopology,
  LogEntry,
  MetricsOverview,
  NodeDetail,
  StateEvolution,
  TimelineEntry,
} from "./types";

export interface ExecutionFilters {
  status?: string;
  thread_id?: string;
  page?: number;
  page_size?: number;
}

function query(filters: ExecutionFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
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
