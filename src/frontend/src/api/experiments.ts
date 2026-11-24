import { getJson } from "./client";
import type { Run } from "./runs.ts";

export interface Experiment {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
}

export function getExperiments(signal?: AbortSignal): Promise<Experiment[]> {
  return getJson<Experiment[]>("/api/v1/experiments", { signal });
}

function assertValidExperimentId(experiment_id: number): void {
  if (!Number.isSafeInteger(experiment_id) || experiment_id < 1) {
    throw new RangeError("Experiment ID must be a positive safe integer.");
  }
}

export function getExperiment(experiment_id: number, signal?: AbortSignal): Promise<Experiment> {
  assertValidExperimentId(experiment_id);
  return getJson<Experiment>(`/api/v1/experiments/${experiment_id}`, { signal });
}

export function getRuns(experiment_id: number, signal?: AbortSignal): Promise<Run[]> {
  assertValidExperimentId(experiment_id);
  return getJson<Run[]>(`/api/v1/experiments/${experiment_id}/runs`, { signal });
}
