import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { ApiError, parseUUID4 } from "../../api/client";
import { getRun, getRunMetrics } from "../../api/runs";
import { MetricChart } from "./MetricChart";
import { preserveMetricCache } from "./metricCache";
import { useLiveRunMetrics } from "./useLiveRunMetricHook";

function formatDate(value: string | null): string {
  if (!value) return "-";
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? "Date unavailable" : new Date(timestamp).toLocaleString();
}

export function RunDetailPage() {
  const { runId } = useParams({ from: "/runs/$runId" });

  const runQuery = useQuery({
    queryKey: ["runs", runId],
    queryFn: ({ signal }) => getRun(parseUUID4(runId), signal),
  });

  const metricsQuery = useQuery({
    queryKey: ["runs", runId, "metrics"],
    queryFn: ({ signal }) => getRunMetrics(parseUUID4(runId), signal),
    enabled: runQuery.isSuccess,
    structuralSharing: preserveMetricCache,
  });

  const run = runQuery.data;
  const isLiveRun = run?.status == "pending" || run?.status == "running";
  const liveState = useLiveRunMetrics(run?.id, isLiveRun);

  if (runQuery.isPending) {
    return (
      <section className="state-panel" aria-live="polite">
        <h1>Loading run...</h1>
      </section>
    );
  }

  if (runQuery.isError || !run) {
    const status = runQuery.error instanceof ApiError ? runQuery.error.status : undefined;

    return (
      <section className="state-panel" aria-labelledby="run-error-title">
        <h1 id="run-error-title">{status === 404 ? "Run not found" : "Could not load run"}</h1>
        <p role="alert">
          {status ? `The API request failed (HTTP ${status}).` : "Could not reach API. Check that backend is running."}
        </p>
        <button className="button" onClick={() => void runQuery.refetch()} type="button">
          Try again
        </button>
        <p>
          <Link to="/">Return to experiments</Link>
        </p>
      </section>
    );
  }

  const metricNames = [...new Set((metricsQuery.data ?? []).map((metric) => metric.name))].sort();

  return (
    <section aria-labelledby="run-title">
      <nav aria-label="Breadcrumb" className="breadcrumbs">
        <Link to="/">Experiments</Link>
        <span aria-hidden="true">/</span>
        <Link to="/experiments/$experimentId" params={{ experimentId: run.experiment_id }}>
          Experiment {run.experiment_id}
        </Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{run.name}</span>
      </nav>

      <div className="page-heading">
        <div>
          <h1 id="run-title">{run.name}</h1>
          <p className="muted">{run.model_name}</p>
          {isLiveRun ? (
            <p aria-live="polite" className="muted">
              Live updates: {liveState}
            </p>
          ) : null}
        </div>
        <span className={`status-badge status-${run.status}`}>{run.status}</span>
      </div>

      <dl className="experiment-metadata">
        <div>
          <dt>Run ID</dt>
          <dd>{run.id}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatDate(run.created_at)}</dd>
        </div>
        <div>
          <dt>Started</dt>
          <dd>{formatDate(run.started_at)}</dd>
        </div>
        <div>
          <dt>Finished</dt>
          <dd>{formatDate(run.finished_at)}</dd>
        </div>
      </dl>

      <section aria-labelledby="metrics-title" className="runs-section">
        <h2 id="metrics-title">Metrics</h2>

        {metricsQuery.isPending ? <p aria-live="polite">Loading metrics...</p> : null}

        {metricsQuery.isError ? (
          <div className="state-panel">
            <p role="alert">
              {metricsQuery.error instanceof ApiError
                ? `The metrics request failed (HTTP ${metricsQuery.error.status})`
                : "Could not load metrics. Check that backend is running"}
            </p>
            <button className="button" onClick={() => void metricsQuery.refetch()} type="button">
              Try again
            </button>
          </div>
        ) : null}

        {metricsQuery.data?.length === 0 ? (
          <div className="state-panel">
            <h3>No metrics recorded</h3>
            <p className="muted">Metrics will appear after the run reports them.</p>
          </div>
        ) : null}

        {metricsQuery.data && metricsQuery.data.length > 0 ? (
          <div className="metric-chart-grid">
            {metricNames.map((metricName) => (
              <article className="metric-card" key={metricName}>
                <h3>{metricName}</h3>
                <MetricChart metricName={metricName} metrics={metricsQuery.data} />
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </section>
  );
}
