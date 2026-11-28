import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { UUID4 } from "../../api/client";
import { getRunMetricsAfter, LIVE_METRIC_PAGE_SIZE, type MetricFloat } from "../../api/runs";
import { mergeMetricBatches } from "./metricCache";

type LiveState = "connecting" | "recovering" | "live" | "reconnecting";

interface MetricUpdate {
  type: "metric_update";
  run_id: string;
  metric: MetricFloat;
}

function parseMetricUpdate(raw: string, expectedRunId: string): MetricFloat | null {
  try {
    const message: unknown = JSON.parse(raw);
    if (typeof message !== "object" || message === null) return null;

    const update = message as Partial<MetricUpdate>;
    const metric = update.metric;

    if (
      update.type !== "metric_update" ||
      update.run_id !== expectedRunId ||
      typeof metric !== "object" ||
      metric === null ||
      !Number.isSafeInteger(metric.id) ||
      typeof metric.run_id !== "string" ||
      metric.run_id !== expectedRunId ||
      typeof metric.name !== "string" ||
      typeof metric.value !== "number" ||
      !Number.isFinite(metric.value) ||
      !Number.isSafeInteger(metric.step) ||
      typeof metric.recorded_at !== "string"
    ) {
      return null;
    }

    return metric;
  } catch {
    return null;
  }
}

export function useLiveRunMetrics(run_id: UUID4 | undefined, enabled: boolean): LiveState {
  const queryClient = useQueryClient();
  const [state, setState] = useState<LiveState>("connecting");

  useEffect(() => {
    const queryKey = ["runs", run_id, "metrics"] as const;

    if (!enabled || !run_id) return;

    let stopped = false;
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let retryAttempt = 0;
    let recoveryController: AbortController | undefined;
    let recovering = false;
    let buffered: MetricFloat[] = [];

    const cached = queryClient.getQueryData<MetricFloat[]>(queryKey) ?? [];
    let cursor = cached.reduce((maxId, metric) => Math.max(maxId, metric.id), 0);

    function mergeBatch(batch: readonly MetricFloat[]) {
      if (batch.length === 0) return;

      queryClient.setQueryData<MetricFloat[]>(queryKey, (current = []) => {
        mergeMetricBatches(current, batch);
      });
      cursor = batch.reduce((highestId, metric) => Math.max(highestId, metric.id), cursor);
    }

    function merge(metric: MetricFloat) {
      mergeBatch([metric]);
    }

    async function recover(activeSocket: WebSocket) {
      if (!run_id) return;

      recovering = true;
      setState("recovering");

      try {
        while (!stopped) {
          const page = await getRunMetricsAfter(run_id, cursor, recoveryController?.signal);

          if (page.length === 0) break;

          mergeBatch(page);

          if (page.length < LIVE_METRIC_PAGE_SIZE) break;
        }

        const bufferedBatch = buffered.toSorted((a, b) => a.id - b.id);
        buffered = [];
        mergeBatch(bufferedBatch);

        recovering = false;
        setState("live");
        retryAttempt = 0;
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          return;
        }

        if (stopped || activeSocket !== socket) return;

        setState("reconnecting");
        activeSocket.close();
      }
    }

    function connect() {
      if (stopped) return;
      if (!run_id) return;

      setState(retryAttempt === 0 ? "connecting" : "reconnecting");

      const url = new URL(`/ws/runs/${run_id}`, window.location.href);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      const currentSocket = new WebSocket(url);
      socket = currentSocket;

      currentSocket.onopen = () => {
        retryAttempt = 0;
        recoveryController = new AbortController();
        void recover(currentSocket);
      };

      currentSocket.onmessage = (event) => {
        if (socket !== currentSocket || currentSocket.readyState !== WebSocket.OPEN || typeof event.data !== "string")
          return;

        const metric = parseMetricUpdate(event.data, run_id);
        if (!metric) return;

        if (recovering) buffered.push(metric);
        else merge(metric);
      };

      currentSocket.onerror = () => currentSocket.close();

      currentSocket.onclose = () => {
        recoveryController?.abort();
        recovering = false;
        buffered = [];

        if (stopped) return;

        // exponential backoff
        const delay = Math.min(1000 * 2 ** retryAttempt, 30_000);
        retryAttempt += 1;
        retryTimer = setTimeout(connect, delay + Math.random() * 250);
      };
    }

    connect();

    return () => {
      stopped = true;
      recoveryController?.abort();
      if (retryTimer) clearTimeout(retryTimer);
      socket?.close();
    };
  }, [enabled, queryClient, run_id]);

  return state;
}
