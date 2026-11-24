import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "../test/mockResponse";
import { ApiError, assertUUID4, getJson, isUUID4, parseUUID4 } from "./client";

describe("UUID4 helpers", () => {
  it("recognizes version 4 UUIDs and returns the branded value", () => {
    const value = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11";

    expect(isUUID4(value)).toBe(true);
    expect(parseUUID4(value)).toBe(value);
    expect(() => assertUUID4(value)).not.toThrow();
  });

  it("rejects malformed values and UUIDs of another version", () => {
    expect(isUUID4("not-a-uuid")).toBe(false);
    expect(isUUID4("a0eebc99-9c0b-1ef8-bb6d-6bb9bd380a11")).toBe(false);
    expect(() => parseUUID4("not-a-uuid")).toThrow(TypeError);
    expect(() => assertUUID4("not-a-uuid")).toThrow(TypeError);
  });
});

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
