from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
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
