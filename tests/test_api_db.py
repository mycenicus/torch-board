from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from board import main
from board.db import database
from board.db.models import Experiment, Run


def configure_database(monkeypatch: pytest.MonkeyPatch, url: str) -> Engine:
    """Inject an isolated engine without reloading mapped ORM modules."""
    in_memory = database.is_in_memory_sqlite_url(url)
    engine_url = url
    options: dict[str, object] = {"echo": False}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    if in_memory:
        engine_url = (
            f"sqlite:///file:torch_board_test_{uuid4().hex}"
            "?mode=memory&cache=shared&uri=true"
        )
        options["poolclass"] = QueuePool

    engine = create_engine(engine_url, **options)
    session_factory = sessionmaker(bind=engine)

    # The lifespan reads these module settings; get_db reads database.SessionLocal.
    monkeypatch.setattr(database, "DATABASE_URL", url)
    monkeypatch.setattr(database, "IS_IN_MEMORY_DB", in_memory)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    monkeypatch.setattr(main, "IS_IN_MEMORY_DB", in_memory)
    monkeypatch.setattr(main, "SessionLocal", session_factory)
    return engine


@pytest.mark.parametrize(
    ("db_url", "expect_create_all"),
    [
        ("file", False),
        ("sqlite://", True),
        ("sqlite:///:memory:", True),
    ],
)
def test_lifespan_calls_create_all_only_for_in_memory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    db_url: str,
    expect_create_all: bool,
) -> None:
    if db_url == "file":
        db_url = f"sqlite:///{tmp_path / 'file_mode.db'}"
    engine = configure_database(monkeypatch, db_url)

    from unittest.mock import MagicMock

    mock_create_all = MagicMock()
    monkeypatch.setattr(database.TelemetryBase.metadata, "create_all", mock_create_all)

    try:
        with TestClient(main.app):
            if expect_create_all:
                mock_create_all.assert_called_once_with(engine)
            else:
                mock_create_all.assert_not_called()
    finally:
        engine.dispose()


def test_in_memory_db_creates_tables_and_persists_api_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = configure_database(monkeypatch, "sqlite://")

    try:
        with TestClient(main.app) as client:
            tables = set(inspect(engine).get_table_names())
            expected_tables = set(database.TelemetryBase.metadata.tables)

            assert expected_tables
            assert expected_tables.issubset(tables)

            experiment_response = client.post(
                "/api/v1/experiments",
                json={"name": "Lifespan test"},
            )
            assert experiment_response.status_code == 201
            experiment_id = experiment_response.json()["id"]

            run_response = client.post(
                f"/api/v1/experiments/{experiment_id}/runs",
                json={"name": "Database check", "model_name": "test-model"},
            )
            assert run_response.status_code == 201
            run_id = run_response.json()["id"]

            read_response = client.get(f"/api/v1/runs/{run_id}")
            assert read_response.status_code == 200
            assert read_response.json()["name"] == "Database check"
    finally:
        engine.dispose()


def test_in_memory_sessions_have_isolated_commit_and_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = configure_database(monkeypatch, "sqlite://")
    database.TelemetryBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    try:
        # A rollback in one session must not discard another session's write.
        first_session = factory()
        first_session.add(Experiment(name="survives other rollback"))
        first_session.flush()

        second_session = factory()
        second_session.scalars(select(Run)).all()
        second_session.rollback()
        second_session.close()

        first_session.commit()
        first_session.close()

        with factory() as verify_session:
            assert (
                verify_session.scalar(
                    select(Experiment).where(
                        Experiment.name == "survives other rollback"
                    )
                )
                is not None
            )

        # A commit in one session must not commit another session's write.
        first_session = factory()
        first_session.add(Experiment(name="must be rolled back"))
        first_session.flush()

        second_session = factory()
        second_session.scalars(select(Run)).all()
        second_session.commit()
        second_session.close()

        first_session.rollback()
        first_session.close()

        with factory() as verify_session:
            assert (
                verify_session.scalar(
                    select(Experiment).where(Experiment.name == "must be rolled back")
                )
                is None
            )
    finally:
        engine.dispose()


def test_file_db_skips_create_all_and_expects_alembic(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    db_file = tmp_path / "test_file_mode.db"
    engine = configure_database(monkeypatch, f"sqlite:///{db_file}")

    try:
        with TestClient(main.app, raise_server_exceptions=False) as client:
            assert inspect(engine).get_table_names() == []

            response = client.get(f"/api/v1/runs/{uuid4()}")
            assert response.status_code == 500
    finally:
        engine.dispose()
