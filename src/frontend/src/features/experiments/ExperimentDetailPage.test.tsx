import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "../../test/mockResponse";
import { renderApp } from "../../test/renderApp";

describe("experiment detail route", () => {
  it("shows not found for an unknown experiment", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 404)));

    renderApp("/experiments/999");

    expect(await screen.findByRole("heading", { name: "Experiment not found" })).toBeInTheDocument();
  });

  it("does not request the API for a malformed experiment ID", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/experiments/not-a-number");

    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows an empty state when an experiment has no runs", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      return Promise.resolve(
        path.endsWith("/runs")
          ? jsonResponse([])
          : jsonResponse({
              id: 2,
              name: "empty experiment",
              description: null,
              created_at: "2026-11-20T10:30:00",
            }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/experiments/2");

    expect(await screen.findByRole("heading", { name: "empty experiment" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "No runs yet" })).toBeInTheDocument();
    expect(screen.getByText("No description")).toBeInTheDocument();
  });

  it("keeps experiment details visible when loading runs fails", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      return Promise.resolve(
        path.endsWith("/runs")
          ? jsonResponse({}, 503)
          : jsonResponse({
              id: 3,
              name: "details survive",
              description: "metadata is available",
              created_at: "2026-11-20T10:30:00",
            }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/experiments/3");

    expect(await screen.findByRole("heading", { name: "details survive" })).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("HTTP 503");
  });
});
