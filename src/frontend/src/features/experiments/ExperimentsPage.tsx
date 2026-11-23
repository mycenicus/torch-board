import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ApiError } from "../../api/client";
import { getExperiments } from "../../api/experiments";

function formatDate(value: string): string {
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? "Date unavailable" : new Date(timestamp).toLocaleString();
}

export function ExperimentsPage() {
  const experimentsQuery = useQuery({
    queryKey: ["experiments"],
    queryFn: ({ signal }) => getExperiments(signal),
  });

  if (experimentsQuery.isPending) {
    return (
      <section className="state-panel" aria-live="polite">
        <h1>Experiments</h1>
        <p>Loading experiments…</p>
      </section>
    );
  }

  if (!experimentsQuery.data) {
    const message =
      experimentsQuery.error instanceof ApiError
        ? `The API request failed (HTTP ${experimentsQuery.error.status}).`
        : "Could not reach the API. Check that the backend is running.";

    return (
      <section className="state-panel" aria-labelledby="experiments-title">
        <h1 id="experiments-title">Experiments</h1>
        <p role="alert">{message}</p>
        <button className="button" onClick={() => void experimentsQuery.refetch()} type="button">
          Try again
        </button>
      </section>
    );
  }

  return (
    <section aria-labelledby="experiments-title">
      <div className="page-heading">
        <div>
          <h1 id="experiments-title">Experiments</h1>
          <p className="muted">Training runs grouped by experiment.</p>
        </div>
      </div>

      {experimentsQuery.isError ? (
        <p className="refresh-warning" role="status">
          Could not refresh the experiment list. Showing the last loaded data.
          <button className="text-button" onClick={() => void experimentsQuery.refetch()} type="button">
            Retry
          </button>
        </p>
      ) : null}

      {experimentsQuery.data.length === 0 ? (
        <div className="state-panel">
          <h2>No experiments yet</h2>
          <p className="muted">Experiments will appear here after a training run is created.</p>
        </div>
      ) : (
        <ul className="experiment-list">
          {experimentsQuery.data.map((experiment) => (
            <li className="experiment-card" key={experiment.id}>
              <Link
                className="experiment-card-link"
                to="/experiments/$experimentId"
                params={{ experimentId: experiment.id }}
              >
                <div className="experiment-card">
                  <div>
                    <h2>{experiment.name}</h2>
                    <p className="muted">{experiment.description || "No description"}</p>
                  </div>
                  <time dateTime={experiment.created_at}>Created {formatDate(experiment.created_at)}</time>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
