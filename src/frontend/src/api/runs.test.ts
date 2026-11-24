import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "../test/mockResponse";
import { parseUUID4 } from "./client";
import { getRun, getRunMetrics } from "./runs";

const runId = parseUUID4("a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11");

describe("run API helpers", () => {
  it("fetches a run and forwards its abort signal", async () => {
    const run = { id: runId, name: "baseline" };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(run));
    const signal = new AbortController().signal;
    vi.stubGlobal("fetch", fetchMock);

    await expect(getRun(runId, signal)).resolves.toEqual(run);

    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/runs/${runId}`, {
      headers: { Accept: "application/json" },
      signal,
    });
  });

  it("fetches historical metrics for a run", async () => {
    const metrics = [{ id: 1, run_id: runId, name: "loss", value: 0.2, step: 3 }];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(metrics));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getRunMetrics(runId)).resolves.toEqual(metrics);

    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/runs/${runId}/metrics`, {
      headers: { Accept: "application/json" },
      signal: undefined,
    });
  });

  it("rejects invalid UUID4 values before fetching", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    expect(() => getRun("not-a-uuid" as typeof runId)).toThrow(TypeError);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
