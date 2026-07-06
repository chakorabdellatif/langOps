// Typed fetch wrapper: base URL + error normalization.
// API types are generated from the backend OpenAPI schema into
// ./generated/ (npm run generate:api) — never hand-write telemetry types.

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    // Backend error body contract: { code, message, detail }
    const body = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      body?.code ?? "unknown_error",
      body?.message ?? response.statusText,
    );
  }
  return response.json() as Promise<T>;
}
