import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { ApiError } from "../../api/client";
import { getExperiment, getRuns } from "../../api/experiments";

function formatDate(value: string): string {
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? "Date unavailable" : new Date(timestamp).toLocaleString();
}

function ExperimentError({ status, onRetry }: { status?: number; onRetry: () => void }) {
  if (status === 404) {
    return (
      <section className="state-panel" aria-labelledby="experiment-error-title">
        <h1 id="experiment-error-title">Experiment not found</h1>
        <p className="muted">This experiment may have been deleted or the link may be incorrect.</p>
        <Link to="/">Return to experiments</Link>
      </section>
    );
  }

  return (
    <section className="state-panel" aria-labelledby="experiment-error-title">
      <h1 id="experiment-error-title">Could not load experiment</h1>
      <p role="alert">
        {status
          ? `The API request failed (HTTP ${status}).`
          : "Could not reach the API. Check that the backend is running."}
      </p>
      <button className="button" onClick={onRetry} type="button">
        Try again
      </button>
    </section>
  );
}

export function ExperimentDetailPage() {
  const { experimentId } = useParams({ from: "/experiments/$experimentId" });
  const experimentQuery = useQuery({
    queryKey: ["experiments", experimentId],
    queryFn: ({ signal }) => getExperiment(experimentId, signal),
  });
  const runsQuery = useQuery({
    queryKey: ["experiments", experimentId, "runs"],
    queryFn: ({ signal }) => getRuns(experimentId, signal),
  });

  if (experimentQuery.isPending) {
    return (
      <section className="state-panel" aria-live="polite">
        <h1>Loading experiment…</h1>
      </section>
    );
  }

  if (!experimentQuery.data) {
    return (
      <ExperimentError
        status={experimentQuery.error instanceof ApiError ? experimentQuery.error.status : undefined}
        onRetry={() => void experimentQuery.refetch()}
      />
    );
  }

  const experiment = experimentQuery.data;

  return (
    <section aria-labelledby="experiment-title">
      <nav aria-label="Breadcrumb" className="breadcrumbs">
        <Link to="/">Experiments</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{experiment.name}</span>
      </nav>

      <div className="page-heading">
        <div>
          <h1 id="experiment-title">{experiment.name}</h1>
          <p className="muted">{experiment.description || "No description"}</p>
        </div>
      </div>

      <dl className="experiment-metadata">
        <div>
          <dt>Experiment ID</dt>
          <dd>{experiment.id}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>
            <time dateTime={experiment.created_at}>{formatDate(experiment.created_at)}</time>
          </dd>
        </div>
      </dl>

      <section aria-labelledby="runs-title" className="runs-section">
        <div className="page-heading">
          <div>
            <h2 id="runs-title">Runs</h2>
            <p className="muted">Training runs associated with this experiment.</p>
          </div>
        </div>

        {runsQuery.isPending ? <p aria-live="polite">Loading runs…</p> : null}

        {runsQuery.isError ? (
          <div className="state-panel">
            <p role="alert">
              {runsQuery.error instanceof ApiError
                ? `The runs request failed (HTTP ${runsQuery.error.status}).`
                : "Could not load runs. Check that the backend is running."}
            </p>
            <button className="button" onClick={() => void runsQuery.refetch()} type="button">
              Try again
            </button>
          </div>
        ) : null}

        {runsQuery.data?.length === 0 ? (
          <div className="state-panel">
            <h3>No runs yet</h3>
            <p className="muted">Runs created for this experiment will appear here.</p>
          </div>
        ) : null}

        {runsQuery.data && runsQuery.data.length > 0 ? (
          <div className="run-table-container">
            <table className="run-table" aria-label={`Runs for ${experiment.name}`}>
              <thead>
                <tr>
                  <th scope="col">Run</th>
                  <th scope="col">Model</th>
                  <th scope="col">Status</th>
                  <th scope="col">Created</th>
                  <th scope="col">Started</th>
                  <th scope="col">Finished</th>
                </tr>
              </thead>
              <tbody>
                {runsQuery.data.map((run) => (
                  <tr key={run.id}>
                    <th scope="row">
                      <Link to="/runs/$runId" params={{ runId: run.id }}>
                        {run.name}
                      </Link>
                    </th>
                    <td>{run.model_name}</td>
                    <td>
                      <span className={`status-badge status-${run.status}`}>{run.status}</span>
                    </td>
                    <td>
                      <time dateTime={run.created_at}>{formatDate(run.created_at)}</time>
                    </td>
                    <td>{run.started_at ? formatDate(run.started_at) : "Not started"}</td>
                    <td>{run.finished_at ? formatDate(run.finished_at) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </section>
  );
}
