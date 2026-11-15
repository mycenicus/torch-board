from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from board.db.database import TelemetryBase, get_db
from board.db.models import Experiment, MetricFloat, Run
from board.main import app


@pytest.fixture
def test_session_factory() -> Generator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TelemetryBase.metadata.create_all(engine)

    factory = sessionmaker(bind=engine)

    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture
def client(
    test_session_factory: sessionmaker[Session],
) -> Generator[TestClient]:
    def override_get_db() -> Generator[Session]:
        with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def create_experiment(
    test_session_factory: sessionmaker[Session],
    name: str = "Test experiment",
    created_at: datetime | None = None,
) -> int:
    with test_session_factory() as session:
        experiment = Experiment(name=name, created_at=created_at)
        session.add(experiment)
        session.commit()
        return experiment.id


# --------------------------- EXPERIMENT -------------------------------------


def test_get_experiments_empty(client: TestClient):
    response = client.get("/api/v1/experiments")

    assert response.status_code == 200
    assert response.json() == []


def test_get_experiments(
    client: TestClient, test_session_factory: sessionmaker[Session]
):
    create_experiment(test_session_factory, "Experiment A")
    create_experiment(test_session_factory, "Experiment B")

    response = client.get("/api/v1/experiments")

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert {experiment["name"] for experiment in data} == {
        "Experiment A",
        "Experiment B",
    }


def test_get_experiments_newest_first(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
):
    create_experiment(
        test_session_factory,
        "Older experiment",
        datetime(2026, 1, 1, tzinfo=UTC),
    )
    create_experiment(
        test_session_factory,
        "Newer experiment",
        datetime(2026, 1, 2, tzinfo=UTC),
    )

    response = client.get("/api/v1/experiments")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == [
        "Newer experiment",
        "Older experiment",
    ]


def test_get_experiment(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
):
    experiment_id = create_experiment(test_session_factory)

    response = client.get(f"/api/v1/experiments/{experiment_id}")

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == experiment_id
    assert data["name"] == "Test experiment"
    assert data["description"] is None
    assert data["created_at"] is not None


def test_get_experiment_not_found(client: TestClient):
    response = client.get("/api/v1/experiments/999")

    assert response.status_code == 404


def test_create_experiment(client: TestClient):
    response = client.post(
        "/api/v1/experiments",
        json={
            "name": "Test experiment",
            "description": "A test description",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] is not None
    assert data["name"] == "Test experiment"
    assert data["description"] == "A test description"
    assert data["created_at"] is not None


def test_create_experiment_without_description(client: TestClient):
    response = client.post(
        "/api/v1/experiments",
        json={"name": "Test experiment"},
    )

    assert response.status_code == 201
    assert response.json()["description"] is None


@pytest.mark.parametrize(
    "name",
    [
        "",
        "a" * 31,
    ],
)
def test_create_experiment_with_invalid_name(
    client: TestClient,
    name: str,
):
    response = client.post(
        "/api/v1/experiments",
        json={"name": name},
    )

    assert response.status_code == 422


# -------------------- EXPERIMENT RUNS ---------------------------------------


def create_run(
    test_session_factory: sessionmaker[Session],
    experiment_id: int,
    name: str = "Test run",
    created_at: datetime | None = None,
) -> UUID:
    with test_session_factory() as session:
        run = Run(
            experiment_id=experiment_id,
            name=name,
            model_name="ResNet18",
            created_at=created_at,
        )
        session.add(run)
        session.commit()
        return run.id


def test_get_experiment_runs_empty(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
):
    experiment_id = create_experiment(test_session_factory)

    response = client.get(f"/api/v1/experiments/{experiment_id}/runs")

    assert response.status_code == 200
    assert response.json() == []


def test_get_experiment_runs_not_found(client: TestClient):
    response = client.get("/api/v1/experiments/999/runs")

    assert response.status_code == 404


def test_get_experiment_runs(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
):
    experiment_id = create_experiment(test_session_factory)

    create_run(test_session_factory, experiment_id, "Run A")
    create_run(test_session_factory, experiment_id, "Run B")

    response = client.get(f"/api/v1/experiments/{experiment_id}/runs")

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert {run["name"] for run in data} == {"Run A", "Run B"}

    for run in data:
        assert run["experiment_id"] == experiment_id
        assert run["status"] == "pending"
        assert run["model_name"] == "ResNet18"


def test_get_experiment_runs_newest_first(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
):
    experiment_id = create_experiment(test_session_factory)

    create_run(
        test_session_factory,
        experiment_id,
        "Older run",
        datetime(2026, 1, 1, tzinfo=UTC),
    )
    create_run(
        test_session_factory,
        experiment_id,
        "Newer run",
        datetime(2026, 1, 2, tzinfo=UTC),
    )

    response = client.get(f"/api/v1/experiments/{experiment_id}/runs")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == [
        "Newer run",
        "Older run",
    ]


# -------------------------- RUN ---------------------------------------------


def test_get_run(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
):
    experiment_id = create_experiment(test_session_factory)
    run_id = create_run(test_session_factory, experiment_id)

    response = client.get(f"/api/v1/runs/{run_id}")

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == str(run_id)
    assert data["experiment_id"] == experiment_id
    assert data["name"] == "Test run"
    assert data["model_name"] == "ResNet18"
    assert data["status"] == "pending"
    assert data["created_at"] is not None


def test_get_run_not_found(client: TestClient):
    response = client.get(f"/api/v1/runs/{uuid4()}")

    assert response.status_code == 404


def test_get_run_invalid_uuid(client: TestClient):
    response = client.get("/api/v1/runs/not-a-uuid")

    assert response.status_code == 422


def test_create_run(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
):
    # First create an experiment.
    experiment_response = client.post(
        "/api/v1/experiments",
        json={"name": "Test experiment"},
    )

    experiment_id = experiment_response.json()["id"]

    # Then create a run belonging to that experiment.
    response = client.post(
        f"/api/v1/experiments/{experiment_id}/runs",
        json={
            "name": "First run",
            "model_name": "transformer",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] is not None
    assert data["experiment_id"] == experiment_id
    assert data["name"] == "First run"
    assert data["model_name"] == "transformer"
    assert data["status"] == "pending"
    assert data["created_at"] is not None

    # Verify that the run was actually persisted.
    with test_session_factory() as session:
        run = session.scalar(select(Run).where(Run.experiment_id == experiment_id))

        assert run is not None
        assert run.name == "First run"


def test_create_run_for_nonexistent_experiment(client: TestClient):
    response = client.post(
        "/api/v1/experiments/999/runs",
        json={
            "name": "First run",
            "model_name": "transformer",
        },
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "model_name": "transformer"},
        {"name": "First run", "model_name": ""},
    ],
)
def test_create_run_with_invalid_data(
    client: TestClient,
    payload: dict[str, str],
):
    experiment_response = client.post(
        "/api/v1/experiments",
        json={"name": "Test experiment"},
    )
    experiment_id = experiment_response.json()["id"]

    response = client.post(
        f"/api/v1/experiments/{experiment_id}/runs",
        json=payload,
    )

    assert response.status_code == 422


# -------------------------- METRICFLOAT -------------------------------------


def create_run_with_metrics(
    test_session_factory: sessionmaker[Session],
) -> str:
    with test_session_factory() as session:
        experiment = Experiment(name="Test experiment")

        run = Run(
            experiment=experiment,
            name="Test run",
            model_name="ResNet18",
        )

        # Intentionally insert metrics out of step order.
        run.metrics = [
            MetricFloat(name="lr", value=0.001, step=2),
            MetricFloat(name="loss", value=0.9, step=1),
            MetricFloat(name="gradient_norm", value=1.5, step=1),
            MetricFloat(name="loss", value=0.7, step=2),
        ]

        session.add(experiment)
        session.commit()

        return str(run.id)


def test_get_run_metrics_empty(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
):
    with test_session_factory() as session:
        experiment = Experiment(name="Test experiment")
        run = Run(
            experiment=experiment,
            name="Test run",
            model_name="ResNet18",
        )
        session.add(experiment)
        session.commit()
        run_id = str(run.id)

    response = client.get(f"/api/v1/runs/{run_id}/metrics")

    assert response.status_code == 200
    assert response.json() == []


def test_get_run_metrics_not_found(client: TestClient):
    response = client.get(f"/api/v1/runs/{uuid4()}/metrics")

    assert response.status_code == 404


def test_get_run_metrics_invalid_uuid(client: TestClient):
    response = client.get("/api/v1/runs/not-a-uuid/metrics")

    assert response.status_code == 422


def test_get_run_metrics(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
):
    run_id = create_run_with_metrics(test_session_factory)

    response = client.get(f"/api/v1/runs/{run_id}/metrics")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 4

    # All metric names should be returned.
    assert {metric["name"] for metric in data} == {
        "loss",
        "lr",
        "gradient_norm",
    }

    for metric in data:
        assert metric["run_id"] == run_id
        assert isinstance(metric["value"], float)
        assert isinstance(metric["step"], int)
        assert metric["recorded_at"] is not None


def test_get_run_metrics_ordered_by_step_and_id(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
):
    run_id = create_run_with_metrics(test_session_factory)

    response = client.get(f"/api/v1/runs/{run_id}/metrics")

    assert response.status_code == 200

    data = response.json()

    # First sort by step, then by ID for metrics sharing a step.
    expected = sorted(
        data,
        key=lambda metric: (metric["step"], metric["id"]),
    )

    assert data == expected

    assert [metric["step"] for metric in data] == [1, 1, 2, 2]
