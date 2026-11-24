import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "../../test/mockResponse";
import { renderApp } from "../../test/renderApp";

vi.mock("./MetricChart", () => ({
  MetricChart: ({ metricName }: { metricName: string }) => <div aria-label={`${metricName} chart`} />,
}));

const runId = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11";

const run = {
  id: runId,
  experiment_id: 4,
  name: "baseline run",
  model_name: "resnet",
  status: "completed",
  created_at: "2026-11-23T12:00:00Z",
  started_at: "2026-11-23T12:01:00Z",
  finished_at: "2026-11-23T12:05:00Z",
};

function stubRunFetch(metricsResponse: Response = jsonResponse([])) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith("/metrics")) return Promise.resolve(metricsResponse);
    return Promise.resolve(jsonResponse(run));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("run detail route", () => {
  it("opens a run from the experiment run list", async () => {
    const experiment = {
      id: 4,
      name: "vision experiment",
      description: null,
      created_at: run.created_at,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/experiments/4/runs")) return Promise.resolve(jsonResponse([run]));
      if (path.endsWith("/experiments/4")) return Promise.resolve(jsonResponse(experiment));
      if (path.endsWith("/metrics")) return Promise.resolve(jsonResponse([]));
      return Promise.resolve(jsonResponse(run));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderApp("/experiments/4");

    await user.click(await screen.findByRole("link", { name: "baseline run" }));

    expect(await screen.findByRole("heading", { name: "baseline run" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/runs/${runId}`, expect.anything());
  });

  it("shows run metadata and a chart for each metric name", async () => {
    const fetchMock = stubRunFetch(
      jsonResponse([
        { id: 1, run_id: runId, name: "loss", value: 0.25, step: 4, recorded_at: run.created_at },
        { id: 2, run_id: runId, name: "accuracy", value: 0.9, step: 4, recorded_at: run.created_at },
      ]),
    );

    renderApp(`/runs/${runId}`);

    expect(await screen.findByRole("heading", { name: "baseline run" })).toBeInTheDocument();
    expect(screen.getByText("resnet")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(await screen.findByLabelText("loss chart")).toBeInTheDocument();
    expect(screen.getByLabelText("accuracy chart")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/runs/${runId}`, expect.anything());
    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/runs/${runId}/metrics`, expect.anything());
  });

  it("shows an empty state when the run has no metrics", async () => {
    stubRunFetch();

    renderApp(`/runs/${runId}`);

    expect(await screen.findByRole("heading", { name: "No metrics recorded" })).toBeInTheDocument();
  });

  it("shows a not-found state when the run does not exist", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}, 404));
    vi.stubGlobal("fetch", fetchMock);

    renderApp(`/runs/${runId}`);

    expect(await screen.findByRole("heading", { name: "Run not found" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows a separate error when metrics cannot be loaded", async () => {
    stubRunFetch(jsonResponse({}, 503));

    renderApp(`/runs/${runId}`);

    expect(await screen.findByRole("heading", { name: "baseline run" })).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("HTTP 503");
  });

  it("rejects malformed UUIDs before calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/runs/not-a-uuid");

    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
