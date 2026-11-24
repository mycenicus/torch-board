/**
 * Create chart component using uPlot
 */

import { useEffect, useMemo, useRef } from "react";
import uPlot from "uplot";
import type { MetricFloat } from "../../api/runs";
import { toMetricChartData } from "./metricChartData";

interface MetricChartProps {
  metricName: string;
  metrics: MetricFloat[];
}

const CHART_HEIGHT = 260;

// Chart component, uPlot handles plot inside of it
export function MetricChart({ metricName, metrics }: MetricChartProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<uPlot | null>(null);
  const data = useMemo(() => toMetricChartData(metrics, metricName), [metrics, metricName]);
  const dataRef = useRef(data); // for resize callback without recreating the whole chart

  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const resizeObserver = new ResizeObserver(([entry]) => {
      if (!entry) return;
      const width = Math.floor(entry.contentRect.width);
      if (width <= 0) return;

      if (!chartRef.current) {
        chartRef.current = new uPlot(
          {
            mode: 1,
            width,
            height: CHART_HEIGHT,
            scales: { x: { time: false } },
            series: [
              {},
              {
                label: metricName,
                stroke: "#2563eb",
                width: 2,
              },
            ],
            axes: [{ label: "Training step" }, { label: metricName }],
          },
          dataRef.current,
          root,
        );
      } else {
        chartRef.current.setSize({ width, height: CHART_HEIGHT });
      }
    });

    resizeObserver.observe(root);

    return () => {
      resizeObserver.disconnect();
      chartRef.current?.destroy();
      chartRef.current = null;
    };
  }, [metricName]);

  useEffect(() => {
    chartRef.current?.setData(data);
  }, [data]);

  return <div aria-label={`${metricName} chart`} className="metric-chart" ref={rootRef} />;
}
