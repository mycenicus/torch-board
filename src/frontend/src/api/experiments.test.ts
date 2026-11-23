import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "../test/mockResponse";
import { getExperiment, getRuns } from "./experiments";

describe("experiment API helpers", () => {
  it("requests one experiment from its detail endpoint", async () => {
    const response = { id: 4, name: "test", description: null, created_at: "2026-11-20T10:30:00" };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(response));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getExperiment(4)).resolves.toEqual(response);

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/experiments/4", expect.anything());
  });

  it("requests the run list for an experiment", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getRuns(8)).resolves.toEqual([]);

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/experiments/8/runs", expect.anything());
  });

  it("rejects invalid experiment IDs before making a request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    expect(() => getExperiment(0)).toThrow(RangeError);
    expect(() => getRuns(Number.NaN)).toThrow(RangeError);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
