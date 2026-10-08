import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { ApiError, getJson, postJson } from "@/lib/api/http/shared";

const schema = z.object({ ok: z.boolean() });
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("getJson retry", () => {
  it("retries once on 500 then succeeds", async () => {
    const f = vi.fn().mockResolvedValueOnce(json(500, { detail: "boom" })).mockResolvedValueOnce(json(200, { ok: true }));
    vi.stubGlobal("fetch", f);
    await expect(getJson("/x", schema)).resolves.toEqual({ ok: true });
    expect(f).toHaveBeenCalledTimes(2);
  });

  it("retries once on network error then succeeds", async () => {
    const f = vi.fn().mockRejectedValueOnce(new TypeError("fail")).mockResolvedValueOnce(json(200, { ok: true }));
    vi.stubGlobal("fetch", f);
    await expect(getJson("/x", schema)).resolves.toEqual({ ok: true });
    expect(f).toHaveBeenCalledTimes(2);
  });

  it("surfaces ApiError after the retry also fails (only 2 calls)", async () => {
    const f = vi.fn(async () => json(500, { detail: "down" }));
    vi.stubGlobal("fetch", f);
    await expect(getJson("/x", schema)).rejects.toMatchObject({ status: 500, detail: "down" });
    expect(f).toHaveBeenCalledTimes(2);
  });

  it("does not retry 4xx", async () => {
    const f = vi.fn(async () => json(422, { detail: "bad" }));
    vi.stubGlobal("fetch", f);
    await expect(getJson("/x", schema)).rejects.toBeInstanceOf(ApiError);
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("does not retry POST on 500 or network error", async () => {
    const f = vi.fn(async () => json(500, { detail: "x" }));
    vi.stubGlobal("fetch", f);
    await expect(postJson("/x", {}, schema)).rejects.toMatchObject({ status: 500 });
    expect(f).toHaveBeenCalledTimes(1);
    const g = vi.fn().mockRejectedValue(new TypeError("fail"));
    vi.stubGlobal("fetch", g);
    await expect(postJson("/x", {}, schema)).rejects.toMatchObject({ status: 0 });
    expect(g).toHaveBeenCalledTimes(1);
  });
});
