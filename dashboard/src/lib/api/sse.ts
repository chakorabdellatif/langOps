"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Subscribe to the backend SSE stream and invalidate execution queries on each
 * `execution.updated` event, so lists and detail views refresh live.
 */
export function useLiveUpdates(): void {
  const queryClient = useQueryClient();
  useEffect(() => {
    const source = new EventSource(`${BASE_URL}/api/v1/events`);
    source.onmessage = () => {
      queryClient.invalidateQueries({ queryKey: ["executions"] });
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
    };
    source.onerror = () => source.close();
    return () => source.close();
  }, [queryClient]);
}
