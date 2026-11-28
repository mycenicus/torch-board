import type { MetricFloat } from "../../api/runs";

export function mergeMetricBatches(current: readonly MetricFloat[], incoming: readonly MetricFloat[]): MetricFloat[] {
  const byId = new Map<number, MetricFloat>();

  for (const metric of current) byId.set(metric.id, metric);
  for (const metric of incoming) byId.set(metric.id, metric);

  return [...byId.values()].toSorted((a, b) => a.step - b.step || a.id - b.id);
}

export function preserveMetricCache(oldData: unknown, newData: unknown): unknown {
  if (!Array.isArray(newData) || !Array.isArray(oldData)) {
    return newData;
  }

  const current = oldData as MetricFloat[];
  const snapshot = newData as MetricFloat[];
  const snapshotIds = new Set(snapshot.map((metric) => metric.id));

  // The updater or snapshot already contains every cached ID.
  // Returning it avoids rebuilding and sorting the cache a second time.
  if (current.every((metric) => snapshotIds.has(metric.id))) {
    return snapshot;
  }

  // Preserve cache additions that arrived after the snapshot request began.
  return mergeMetricBatches(current, snapshot);
}
