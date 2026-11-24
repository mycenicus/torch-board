/**
 * Translate backend's MetricFloat points to uPlot chart points
 */

import type { MetricFloat } from "../../api/runs";

export type MetricChartData = [number[], (number | null)[]];

export function toMetricChartData(metrics: MetricFloat[], metricName: string): MetricChartData {
  const points = metrics
    .filter((metric) => metric.name === metricName)
    .toSorted((a, b) => a.step - b.step || a.id - b.id);

  return [
    points.map((point) => point.step), // x
    points.map((point) => point.value), // y
  ];
}
