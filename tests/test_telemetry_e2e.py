"""
E2E tests

1. Send POST with metrics, retrieve them back. Tests persistance and endpoints
2. Send POST with run.start and run.end and with metrics, check if run is persisted correctly
3. Send incorrect messages and then send correct to see if everything is ok
"""

import time
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from board.db.database import TelemetryBase, get_db
from board.db.models import Experiment, Run
from board.main import app


@pytest.fixture
def test_session_factory() -> Generator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection: Any, record: Any) -> None:
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
    original_overrides = app.dependency_overrides.copy()
    had_original_factory = hasattr(app.state, "session_factory")
    original_factory = getattr(app.state, "session_factory", None)

    app.state.session_factory = test_session_factory

    def override_get_db() -> Generator[Session]:
        with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)

        if had_original_factory:
            app.state.session_factory = original_factory
        else:
            del app.state.session_factory


def create_run(
    session_factory: sessionmaker[Session],
) -> UUID:
    with session_factory.begin() as session:
        experiment = Experiment(name="E2E experiment")
        run = Run(
            experiment=experiment,
            name="E2E run",
            model_name="ResNet18",
        )
        session.add(run)
        session.flush()

        run_id = run.id

    return run_id


def make_message(
    run_id: UUID,
    event_type: str,
    payload: dict[str, Any],
    timestamp: datetime,
    sequence: int = 1,
) -> dict[str, Any]:
    return {
        "run_id": str(run_id),
        "timestamp": timestamp.isoformat(),
        "sequence": sequence,
        "event_type": event_type,
        "source": {
            "machine_id": "e2e-test-machine",
            "hostname": "localhost",
            "software_version": "test",
        },
        "payload": payload,
    }


def wait_for_metrics(
    client: TestClient,
    run_id: UUID,
    expected_count: int,
    timeout: float = 5.0,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/runs/{run_id}/metrics")

        if response.status_code == 200:
            metrics = response.json()

            if len(metrics) == expected_count:
                return metrics

        time.sleep(0.02)

    pytest.fail(
        f"Expected {expected_count} metrics for run {run_id} within {timeout} seconds"
    )


def wait_for_run_status(
    client: TestClient,
    run_id: UUID,
    expected_status: str,
    timeout: float = 5.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/runs/{run_id}")

        if response.status_code == 200:
            run = response.json()

            if run["status"] == expected_status:
                return run

        time.sleep(0.02)

    pytest.fail(
        f"Run {run_id} did not reach status {expected_status!r} "
        f"within {timeout} seconds"
    )


def test_metrics_persisted_through_telemetry_api(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
) -> None:
    run_id = create_run(test_session_factory)
    timestamp = datetime(2032, 11, 16, 10, 0, tzinfo=UTC)

    message = make_message(
        run_id=run_id,
        event_type="metrics.batch",
        timestamp=timestamp,
        payload={
            "step": 10,
            "metrics": [
                {"name": "loss", "value": 0.42},
                {"name": "accuracy", "value": 0.95},
            ],
        },
    )

    response = client.post("/api/v1/telemetry", json=message)

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"

    metrics = wait_for_metrics(client, run_id, expected_count=2)

    assert {metric["name"] for metric in metrics} == {"loss", "accuracy"}

    loss = next(metric for metric in metrics if metric["name"] == "loss")
    accuracy = next(metric for metric in metrics if metric["name"] == "accuracy")

    assert loss["value"] == pytest.approx(0.42)
    assert accuracy["value"] == pytest.approx(0.95)

    assert all(metric["step"] == 10 for metric in metrics)
    assert all(metric["run_id"] == str(run_id) for metric in metrics)

    for metric in metrics:
        recorded_at = datetime.fromisoformat(metric["recorded_at"])
        assert recorded_at == timestamp.replace(tzinfo=None)


def test_run_lifecycle_persisted_through_telemetry_api(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
) -> None:
    run_id = create_run(test_session_factory)

    started_at = datetime(2032, 11, 16, 10, 0, tzinfo=UTC)

    start_message = make_message(
        run_id=run_id,
        event_type="run.status",
        timestamp=started_at,
        sequence=1,
        payload={"status": "running"},
    )

    response = client.post("/api/v1/telemetry", json=start_message)

    assert response.status_code == 202

    run = wait_for_run_status(client, run_id, "running")

    actual_started_at = datetime.fromisoformat(run["started_at"])
    assert actual_started_at == started_at.replace(tzinfo=None)
    assert run["finished_at"] is None

    finished_at = datetime(2032, 11, 16, 10, 30, tzinfo=UTC)

    finish_message = make_message(
        run_id=run_id,
        event_type="run.status",
        timestamp=finished_at,
        sequence=2,
        payload={"status": "completed"},
    )

    response = client.post("/api/v1/telemetry", json=finish_message)

    assert response.status_code == 202

    run = wait_for_run_status(client, run_id, "completed")

    actual_finished_at = datetime.fromisoformat(run["finished_at"])

    assert actual_started_at == started_at.replace(tzinfo=None)
    assert actual_finished_at == finished_at.replace(tzinfo=None)


def test_worker_survives_processing_errors_and_unsupported_events(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
) -> None:
    run_id = create_run(test_session_factory)

    # First, send an event referencing a nonexistent run.
    invalid_run_message = make_message(
        run_id=uuid4(),
        event_type="run.status",
        timestamp=datetime.now(UTC),
        payload={"status": "running"},
    )

    response = client.post(
        "/api/v1/telemetry",
        json=invalid_run_message,
    )

    assert response.status_code == 202

    # Then send an event type this server does not support.
    unsupported_message = make_message(
        run_id=run_id,
        event_type="future.event",
        timestamp=datetime.now(UTC),
        payload={"some_future_field": "value"},
        sequence=2,
    )

    response = client.post(
        "/api/v1/telemetry",
        json=unsupported_message,
    )

    assert response.status_code == 202

    # Finally, send a valid message. If the worker survived both previous
    # messages, these metrics will eventually be available.
    valid_message = make_message(
        run_id=run_id,
        event_type="metrics.batch",
        timestamp=datetime.now(UTC),
        payload={
            "step": 1,
            "metrics": [{"name": "loss", "value": 0.5}],
        },
        sequence=3,
    )

    response = client.post("/api/v1/telemetry", json=valid_message)

    assert response.status_code == 202

    metrics = wait_for_metrics(client, run_id, expected_count=1)

    assert metrics[0]["name"] == "loss"
    assert metrics[0]["value"] == pytest.approx(0.5)

    status_response = client.get("/api/v1/telemetry/status")

    assert status_response.status_code == 200
    assert status_response.json()["worker_running"] is True
