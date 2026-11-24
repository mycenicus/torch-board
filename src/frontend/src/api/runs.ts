import type { UUID4 } from "./client";
import { assertUUID4, getJson } from "./client";

export type RunStatus = "pending" | "running" | "completed" | "failed";

export interface Run {
  id: UUID4;
  experiment_id: number;
  name: string;
  model_name: string;
  status: RunStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface MetricFloat {
  id: number;
  run_id: UUID4;
  name: string;
  value: number;
  step: number;
  recorded_at: string;
}

export function getRun(run_id: UUID4, signal?: AbortSignal): Promise<Run> {
  assertUUID4(run_id);
  return getJson<Run>(`/api/v1/runs/${run_id}`, { signal });
}

export function getRunMetrics(run_id: UUID4, signal?: AbortSignal): Promise<MetricFloat[]> {
  assertUUID4(run_id);
  return getJson<MetricFloat[]>(`/api/v1/runs/${run_id}/metrics`, { signal });
}
