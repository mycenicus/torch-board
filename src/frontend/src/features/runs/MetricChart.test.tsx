import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { parseUUID4 } from "../../api/client";
import type { MetricFloat } from "../../api/runs";
import { MetricChart } from "./MetricChart";

const uplotMocks = vi.hoisted(() => ({
  constructor: vi.fn(),
  chart: {
    destroy: vi.fn(),
    setData: vi.fn(),
    setSize: vi.fn(),
  },
}));

vi.mock("uplot", () => ({
  default: class UPlotMock {
    constructor(options: unknown, data: unknown, root: HTMLElement) {
      uplotMocks.constructor(options, data, root);
      return uplotMocks.chart;
    }
  },
}));

class ResizeObserverMock {
  static instance: ResizeObserverMock;
  callback: ResizeObserverCallback;
  disconnected = false;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
    ResizeObserverMock.instance = this;
  }

  observe(element: Element) {
    this.resize(640, element);
  }

  disconnect() {
    this.disconnected = true;
  }

  resize(width: number, target: Element) {
    this.callback([{ target, contentRect: { width } } as ResizeObserverEntry], this as unknown as ResizeObserver);
  }
}

const runId = parseUUID4("a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11");

function metric(id: number, step: number, value: number): MetricFloat {
  return {
    id,
    run_id: runId,
    name: "loss",
    value,
    step,
    recorded_at: "2026-11-23T12:00:00Z",
  };
}

describe("MetricChart", () => {
  beforeEach(() => {
    uplotMocks.constructor.mockClear();
    uplotMocks.chart.destroy.mockClear();
    uplotMocks.chart.setData.mockClear();
    uplotMocks.chart.setSize.mockClear();
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
  });

  it("creates one chart, updates its data and size, then cleans up", async () => {
    const firstMetrics = [metric(1, 1, 0.5)];
    const { rerender, unmount, container } = render(<MetricChart metricName="loss" metrics={firstMetrics} />);

    expect(uplotMocks.constructor).toHaveBeenCalledTimes(1);
    expect(uplotMocks.constructor.mock.calls[0][1]).toEqual([[1], [0.5]]);

    const observer = ResizeObserverMock.instance;
    observer.resize(800, container.firstElementChild as Element);
    expect(uplotMocks.chart.setSize).toHaveBeenCalledWith({ width: 800, height: 260 });

    rerender(<MetricChart metricName="loss" metrics={[...firstMetrics, metric(2, 2, 0.25)]} />);

    await waitFor(() => {
      expect(uplotMocks.chart.setData).toHaveBeenLastCalledWith([
        [1, 2],
        [0.5, 0.25],
      ]);
    });
    expect(uplotMocks.constructor).toHaveBeenCalledTimes(1);

    unmount();
    expect(observer.disconnected).toBe(true);
    expect(uplotMocks.chart.destroy).toHaveBeenCalledTimes(1);
  });
});
