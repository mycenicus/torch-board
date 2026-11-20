export class ApiError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`The API returned HTTP ${status}.`);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function getJson<T>(path: string, options: Pick<RequestInit, "signal"> = {}): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    signal: options.signal, // For Tanstack query to abort if you leave the page
  });

  if (!response.ok) {
    throw new ApiError(response.status);
  }

  return (await response.json()) as T;
}
