import { describe, expect, it } from "vitest";
import { parseUUID4 } from "../../api/client";
import type { MetricFloat } from "../../api/runs";
import { toMetricChartData } from "./metricChartData";

const metrics: MetricFloat[] = [
  {
    id: 3,
    run_id: parseUUID4("a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"),
    name: "loss",
    value: 0.25,
    step: 2,
    recorded_at: "2026-11-23T12:00:02Z",
  },
  {
    id: 1,
    run_id: parseUUID4("a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"),
    name: "loss",
    value: 0.5,
    step: 1,
    recorded_at: "2026-11-23T12:00:01Z",
  },
  {
    id: 2,
    run_id: parseUUID4("a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"),
    name: "loss",
    value: 0.4,
    step: 1,
    recorded_at: "2026-11-23T12:00:01Z",
  },
];

describe("toMetricChartData", () => {
  it("sorts by step and ID while retaining duplicate steps", () => {
    expect(toMetricChartData(metrics, "loss")).toEqual([
      [1, 1, 2],
      [0.5, 0.4, 0.25],
    ]);
  });

  it("returns empty arrays for a metric with no points", () => {
    expect(toMetricChartData(metrics, "learning_rate")).toEqual([[], []]);
  });
});
