// Shared helpers for the HTTP adapters. No domain logic, no fixtures.
import type { ZodType } from "zod";

export const API_BASE = (process.env.NEXT_PUBLIC_STRATA_API_URL || "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const RETRY_DELAY_MS = 300;

export const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** encodeURIComponent for one path segment (never split citations on "/"). */
export const seg = (v: string | number) => encodeURIComponent(String(v));

/** Query-string builder; drops undefined, null and empty-string values. Returns "" or "?a=b". */
export function qs(params?: Record<string, string | number | boolean | null | undefined>): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    sp.append(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export interface GetJsonOpts<T> {
  /** Value to return on HTTP 404 (default: throw ApiError). */
  on404?: T;
  /** Value to return on HTTP 409 "run is still running" (default: throw ApiError). */
  on409?: T;
  signal?: AbortSignal;
}

async function detailOf(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "detail" in body) {
      const d = (body as { detail: unknown }).detail;
      return typeof d === "string" ? d : JSON.stringify(d);
    }
    return JSON.stringify(body);
  } catch {
    return res.statusText || "request failed";
  }
}

async function request(method: "GET" | "POST", path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  try {
    return await fetch(`${API_BASE}${path}`, {
      method,
      headers: body === undefined ? { Accept: "application/json" } : { Accept: "application/json", "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, "Cannot reach the Strata API");
  }
}

async function handle<T>(res: Response, schema: ZodType<T>, opts?: GetJsonOpts<T>): Promise<T> {
  if (res.status === 404 && opts && "on404" in opts) return opts.on404 as T;
  if (res.status === 409 && opts && "on409" in opts) return opts.on409 as T;
  if (!res.ok) throw new ApiError(res.status, await detailOf(res));
  return schema.parse(await res.json());
}

/** GET `path`, zod-parse the JSON body. 404/409 map to opts.on404/on409 when provided. */
export async function getJson<T>(path: string, schema: ZodType<T>, opts?: GetJsonOpts<T>): Promise<T> {
  // Retry once (GET only) on network failure or 5xx: the API may drop a pooled DB connection after idle.
  let res: Response;
  try {
    res = await request("GET", path, undefined, opts?.signal);
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 0) throw e;
    await sleep(RETRY_DELAY_MS);
    res = await request("GET", path, undefined, opts?.signal);
  }
  if (res.status >= 500) {
    await sleep(RETRY_DELAY_MS);
    res = await request("GET", path, undefined, opts?.signal);
  }
  return handle(res, schema, opts);
}

/** POST JSON, zod-parse the response. Same 404/409 handling as getJson. */
export async function postJson<T>(path: string, body: unknown, schema: ZodType<T>, opts?: GetJsonOpts<T>): Promise<T> {
  return handle(await request("POST", path, body, opts?.signal), schema, opts);
}
