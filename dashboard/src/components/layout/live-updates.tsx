"use client";

import { useLiveUpdates } from "@/lib/api/sse";

/** Mounts the SSE subscription once, app-wide. Renders nothing. */
export function LiveUpdates() {
  useLiveUpdates();
  return null;
}
