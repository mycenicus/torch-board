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

declare const __brand: unique symbol;
export type UUID4 = string & { readonly [__brand]: "UUID4" };

const UUID4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isUUID4(value: unknown): value is UUID4 {
  return typeof value === "string" && UUID4_REGEX.test(value);
}

export function assertUUID4(value: unknown): asserts value is UUID4 {
  if (typeof value !== "string" || !UUID4_REGEX.test(value)) {
    throw new TypeError(`Invalid UUID4: ${String(value)}`);
  }
}

export function parseUUID4(value: unknown): UUID4 {
  if (!isUUID4(value)) {
    throw new TypeError(`Invalid UUID4: ${String(value)}`);
  }
  return value;
}
