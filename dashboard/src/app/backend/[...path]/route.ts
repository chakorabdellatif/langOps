// Server-side proxy to the LangOps API. Lets the dashboard talk to an
// API protected by LANGOPS_API_KEY without ever shipping the key to the
// browser: the key is read from the server environment and attached here.
//
// Enable by setting NEXT_PUBLIC_API_URL="/backend" (so the client calls this
// route) plus BACKEND_URL + LANGOPS_API_KEY in the server environment. When
// auth is off (the default), the client can talk to the backend directly and
// this route is simply unused.

import { type NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const API_KEY = process.env.LANGOPS_API_KEY ?? "";

export const dynamic = "force-dynamic";

async function proxy(req: NextRequest, path: string[]): Promise<Response> {
  const search = req.nextUrl.search;
  const target = `${BACKEND_URL}/${path.join("/")}${search}`;
  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const accept = req.headers.get("accept");
  if (accept) headers.set("accept", accept);
  if (API_KEY) headers.set("authorization", `Bearer ${API_KEY}`);

  const init: RequestInit = { method: req.method, headers };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  const upstream = await fetch(target, init);
  // Stream the response body through unchanged (works for JSON and SSE).
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "cache-control": upstream.headers.get("cache-control") ?? "no-store",
    },
  });
}

export async function GET(req: NextRequest, ctx: { params: { path: string[] } }) {
  return proxy(req, ctx.params.path);
}

export async function POST(req: NextRequest, ctx: { params: { path: string[] } }) {
  return proxy(req, ctx.params.path);
}
