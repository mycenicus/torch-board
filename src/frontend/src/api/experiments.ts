import { getJson } from "./client";

export interface Experiment {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
}

export function getExperiments(signal?: AbortSignal): Promise<Experiment[]> {
  return getJson<Experiment[]>("/api/v1/experiments", { signal });
}

export type RunStatus = "pending" | "running" | "completed" | "failed";

export interface Run {
  id: string;
  experiment_id: number;
  name: string;
  model_name: string;
  status: RunStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

function assertValidExperimentId(experimentId: number): void {
  if (!Number.isSafeInteger(experimentId) || experimentId < 1) {
    throw new RangeError("Experiment ID must be a positive safe integer.");
  }
}

export function getExperiment(experimentId: number, signal?: AbortSignal): Promise<Experiment> {
  assertValidExperimentId(experimentId);
  return getJson<Experiment>(`/api/v1/experiments/${experimentId}`, { signal });
}

export function getRuns(experimentId: number, signal?: AbortSignal): Promise<Run[]> {
  assertValidExperimentId(experimentId);
  return getJson<Run[]>(`/api/v1/experiments/${experimentId}/runs`, { signal });
}
