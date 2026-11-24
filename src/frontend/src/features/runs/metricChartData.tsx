/**
 * Translate backend's MetricFloat points to uPlot chart points
 */

import type { MetricFloat } from "../../api/runs";

export type MetricChartData = [number[], (number | null)[]];

export function toMetricChartData(metrics: MetricFloat[], metricName: string): MetricChartData {
  // if metrics have same step, keep the with the greatest id
  // required by uPlot: x must be unique and in ascending order
  const latestPointByStep = new Map<number, MetricFloat>();

  for (const point of metrics) {
    if (point.name !== metricName) continue;

    const latest = latestPointByStep.get(point.step);
    if (!latest || point.id > latest.id) {
      latestPointByStep.set(point.step, point);
    }
  }

  const points = [...latestPointByStep.values()].toSorted((a, b) => a.step - b.step);

  return [
    points.map((point) => point.step), // x
    points.map((point) => point.value), // y
  ];
}
