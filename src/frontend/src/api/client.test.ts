import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "../test/mockResponse";
import { ApiError, getJson } from "./client";

describe("getJson", () => {
  it("returns JSON from a successful response", async () => {
    const body = [{ id: 1, name: "baseline" }];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(body)));

    await expect(getJson<typeof body>("/api/v1/experiments")).resolves.toEqual(body);
  });

  it("throws an ApiError with the HTTP status for a failed response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 503)));

    await expect(getJson("/api/v1/experiments")).rejects.toMatchObject({
      name: ApiError.name,
      status: 503,
    });
  });

  it("passes the abort signal to fetch", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    const signal = new AbortController().signal;
    vi.stubGlobal("fetch", fetchMock);

    await getJson("/api/v1/experiments", { signal });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/experiments", {
      headers: { Accept: "application/json" },
      signal,
    });
  });
});
