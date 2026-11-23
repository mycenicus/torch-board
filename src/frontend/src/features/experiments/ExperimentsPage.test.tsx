import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "../../test/mockResponse";
import { renderApp } from "../../test/renderApp";

describe("experiments navigation", () => {
  it("shows a loading state while experiments are fetched", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );

    renderApp();

    expect(await screen.findByText("Loading experiments…")).toBeInTheDocument();
  });

  it("shows an actionable message when the API is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    renderApp();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not reach the API. Check that the backend is running.",
    );
  });

  it("shows an empty state when there are no experiments", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));

    renderApp();

    expect(await screen.findByRole("heading", { name: "No experiments yet" })).toBeInTheDocument();
  });

  it("links an experiment to its detail route", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse([
          {
            id: 12,
            name: "baseline",
            description: "First training experiment",
            created_at: "2026-11-20T10:30:00",
          },
        ]),
      ),
    );

    renderApp();

    expect(await screen.findByRole("link", { name: /baseline/ })).toHaveAttribute("href", "/experiments/12");
  });

  it("opens an experiment and displays its metadata and runs", async () => {
    const createdAt = "2026-11-20T10:30:00";
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/api/v1/experiments") {
        return Promise.resolve(
          jsonResponse([{ id: 1, name: "baseline", description: "First experiment", created_at: createdAt }]),
        );
      }
      if (path === "/api/v1/experiments/1") {
        return Promise.resolve(
          jsonResponse({ id: 1, name: "baseline", description: "First experiment", created_at: createdAt }),
        );
      }
      if (path === "/api/v1/experiments/1/runs") {
        return Promise.resolve(
          jsonResponse([
            {
              id: "f09580f0-07b6-42ac-bfea-266d01827eac",
              experiment_id: 1,
              name: "run one",
              model_name: "resnet",
              status: "running",
              created_at: createdAt,
              started_at: null,
              finished_at: null,
            },
          ]),
        );
      }
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderApp();
    await user.click(await screen.findByRole("link", { name: /baseline/ }));

    expect(await screen.findByRole("heading", { name: "baseline" })).toBeInTheDocument();
    expect(screen.getByText("First experiment")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Runs for baseline" })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /run one resnet running/ })).toBeInTheDocument();
    expect(screen.getByText("Not started")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/experiments/1", expect.anything());
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/experiments/1/runs", expect.anything());
  });
});
