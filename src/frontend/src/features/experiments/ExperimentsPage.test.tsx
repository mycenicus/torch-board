import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "../../test/mockResponse";
import { ExperimentsPage } from "./ExperimentsPage";

function renderExperimentsPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ExperimentsPage />
    </QueryClientProvider>,
  );
}

describe("ExperimentsPage", () => {
  it("shows a loading state while experiments are fetched", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );

    renderExperimentsPage();

    expect(screen.getByText("Loading experiments…")).toBeInTheDocument();
  });

  it("shows an actionable message when the API is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    renderExperimentsPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not reach the API. Check that the backend is running.",
    );
  });

  it("shows an empty state when there are no experiments", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));

    renderExperimentsPage();

    expect(await screen.findByRole("heading", { name: "No experiments yet" })).toBeInTheDocument();
  });

  it("renders experiment details returned by the API", async () => {
    const createdAt = "2026-11-20T10:30:00";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse([
          {
            id: 1,
            name: "baseline",
            description: "First training experiment",
            created_at: createdAt,
          },
        ]),
      ),
    );

    renderExperimentsPage();

    expect(await screen.findByRole("heading", { name: "baseline" })).toBeInTheDocument();
    expect(screen.getByText("First training experiment")).toBeInTheDocument();
    expect(screen.getByRole("time")).toHaveAttribute("datetime", createdAt);
  });

  it("allows retry after an HTTP error", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({}, 503)).mockResolvedValueOnce(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderExperimentsPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("HTTP 503");
    await user.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("heading", { name: "No experiments yet" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
