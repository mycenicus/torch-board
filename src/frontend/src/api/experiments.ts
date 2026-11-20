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
