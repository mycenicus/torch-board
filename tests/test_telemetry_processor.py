import asyncio
from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from board.db.database import TelemetryBase
from board.db.models import Experiment, MetricFloat, Run
from board.telemetry.processor import UnknownRunError, process_telemetry_message
from board.telemetry.protocol import TelemetryMessage, TelemetrySource


@pytest.fixture
def test_session_factory() -> Generator[sessionmaker[Session]]:
    engine = create_engine("sqlite:///:memory:")

    factory = sessionmaker(bind=engine)

    TelemetryBase.metadata.create_all(engine)

    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture
def existing_run(test_session_factory: sessionmaker[Session]) -> Run:
    with test_session_factory.begin() as session:
        experiment = Experiment(name="Test experiment")
        run = Run(experiment=experiment, name="Run 1", model_name="transformer")
        session.add(run)
        session.flush()

        run_id = run.id

    return Run(id=run_id, name="Run 1", model_name="transformer")


def get_run(test_session_factory: sessionmaker[Session], run_id: UUID) -> Run:
    with test_session_factory() as session:
        run = session.get(Run, run_id)
        assert run is not None
        return run


def make_message_metrics_batch(run_id: UUID) -> TelemetryMessage:
    return TelemetryMessage(
        run_id=run_id,
        source=TelemetrySource(machine_id="some-machine"),
        sequence=1,
        event_type="metrics.batch",
        payload={
            "step": 10,
            "metrics": [
                {"name": "loss", "value": 0.42},
                {"name": "lr", "value": 0.001},
            ],
        },
    )


def make_message_run_status(
    run_id: UUID, timestamp: datetime, status: str
) -> TelemetryMessage:
    return TelemetryMessage(
        timestamp=timestamp,
        run_id=run_id,
        source=TelemetrySource(machine_id="some-machine"),
        sequence=1,
        event_type="run.status",
        payload={"status": status},
    )


def test_persists_multiple_metrics(
    test_session_factory: sessionmaker[Session], existing_run: Run
):
    message = make_message_metrics_batch(existing_run.id)

    asyncio.run(process_telemetry_message(message, test_session_factory))

    with test_session_factory() as session:
        metrics = session.scalars(select(MetricFloat).order_by(MetricFloat.id)).all()

        assert len(metrics) == 2
        assert metrics[0].name == "loss"
        assert metrics[0].value == pytest.approx(0.42)
        assert metrics[0].step == 10
        assert metrics[0].run_id == existing_run.id

        assert metrics[1].name == "lr"
        assert metrics[1].value == pytest.approx(0.001)
        assert metrics[1].step == 10
        assert metrics[1].run_id == existing_run.id


def test_publishes_metrics_only_after_they_are_committed(
    test_session_factory: sessionmaker[Session], existing_run: Run
):
    message = make_message_metrics_batch(existing_run.id)
    published_ids: list[int] = []

    class VerifyingConnectionManager:
        async def publish_metric(self, run_id: UUID, metric: dict[str, object]) -> None:
            assert run_id == existing_run.id
            metric_id = metric["id"]
            assert isinstance(metric_id, int)

            with test_session_factory() as session:
                stored_metric = session.get(MetricFloat, metric_id)

            assert stored_metric is not None
            published_ids.append(metric_id)

    asyncio.run(
        process_telemetry_message(
            message,
            test_session_factory,
            # pyrefly: ignore[bad-argument-type]
            VerifyingConnectionManager(),  # pyright: ignore[reportArgumentType]
        )
    )

    assert len(published_ids) == 2


def test_unknown_run_is_not_persisted(test_session_factory: sessionmaker[Session]):
    message = make_message_metrics_batch(uuid4())

    with pytest.raises(UnknownRunError):
        asyncio.run(process_telemetry_message(message, test_session_factory))

    with test_session_factory() as session:
        metrics = session.scalars(select(MetricFloat)).all()
        assert metrics == []


def test_metrics_are_associated_with_correct_run(
    test_session_factory: sessionmaker[Session],
):
    """
    Creates 2 runs with same metrics, makes sure if we pass a message with uuid
    of second run, then metrics in DB are associated with that run exactly,
    after message is processed
    """
    with test_session_factory.begin() as session:
        experiment = Experiment(name="Test experiment")

        run1 = Run(experiment=experiment, name="Run 1", model_name="transformer")
        run2 = Run(experiment=experiment, name="Run 2", model_name="transformer")

        session.add_all([run1, run2])
        session.flush()

        run1_id = run1.id
        run2_id = run2.id

    message = make_message_metrics_batch(run2_id)

    asyncio.run(process_telemetry_message(message, test_session_factory))

    with test_session_factory() as session:
        metrics = session.scalars(select(MetricFloat)).all()

        assert len(metrics) == 2
        assert all(metric.run_id == run2_id for metric in metrics)
        assert all(metric.run_id != run1_id for metric in metrics)


def test_pending_runs_become_running(
    existing_run: Run, test_session_factory: sessionmaker[Session]
):
    timestamp = datetime(2032, 11, 11, 11, 11, tzinfo=UTC)
    message = make_message_run_status(existing_run.id, timestamp, "running")

    asyncio.run(process_telemetry_message(message, test_session_factory))

    run = get_run(test_session_factory, existing_run.id)

    assert run.status == "running"
    assert run.started_at == timestamp.replace(tzinfo=None)
    assert run.finished_at is None


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_pending_run_can_finish_without_start(
    existing_run: Run, test_session_factory: sessionmaker[Session], status: str
):
    timestamp = datetime(2032, 11, 11, 11, 11, tzinfo=UTC)
    message = make_message_run_status(existing_run.id, timestamp, status)

    asyncio.run(process_telemetry_message(message, test_session_factory))

    run = get_run(test_session_factory, existing_run.id)

    assert run.status == status
    assert run.started_at is None
    assert run.finished_at == timestamp.replace(tzinfo=None)


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_pending_run_can_finish(
    existing_run: Run, test_session_factory: sessionmaker[Session], status: str
):
    started_at = datetime(2032, 11, 11, 11, 0, tzinfo=UTC)
    message_start = make_message_run_status(existing_run.id, started_at, "running")

    asyncio.run(process_telemetry_message(message_start, test_session_factory))

    finished_at = datetime(2032, 11, 11, 11, 11, tzinfo=UTC)
    message_finish = make_message_run_status(existing_run.id, finished_at, status)

    asyncio.run(process_telemetry_message(message_finish, test_session_factory))

    run = get_run(test_session_factory, existing_run.id)

    assert run.status == status
    assert run.started_at == started_at.replace(tzinfo=None)
    assert run.finished_at == finished_at.replace(tzinfo=None)


def test_repeated_running_does_not_overwrite_started_at(
    existing_run: Run, test_session_factory: sessionmaker[Session]
):
    started_at = datetime(2032, 11, 11, 0, 0, tzinfo=UTC)
    message1 = make_message_run_status(existing_run.id, started_at, "running")

    asyncio.run(process_telemetry_message(message1, test_session_factory))

    some_timestamp = datetime(2032, 11, 11, 11, tzinfo=UTC)
    message2 = make_message_run_status(existing_run.id, some_timestamp, "running")

    asyncio.run(process_telemetry_message(message2, test_session_factory))

    run = get_run(test_session_factory, existing_run.id)

    assert run.status == "running"
    assert run.started_at == started_at.replace(tzinfo=None)


@pytest.mark.parametrize(
    ("initial_status", "incoming_status"),
    [
        ("completed", "running"),
        ("completed", "failed"),
        ("completed", "completed"),
        ("failed", "running"),
        ("failed", "completed"),
        ("failed", "failed"),
    ],
)
def test_run_terminal_status_cannot_be_changed(
    existing_run: Run,
    test_session_factory: sessionmaker[Session],
    initial_status: str,
    incoming_status: str,
):
    original_timestamp = datetime(2032, 11, 11, 0, 0, tzinfo=UTC)
    message1 = make_message_run_status(
        existing_run.id, original_timestamp, initial_status
    )

    asyncio.run(process_telemetry_message(message1, test_session_factory))

    incoming_timestamp = datetime(2032, 11, 11, 11, 11, tzinfo=UTC)
    message2 = make_message_run_status(
        existing_run.id, incoming_timestamp, incoming_status
    )

    asyncio.run(process_telemetry_message(message2, test_session_factory))

    run = get_run(test_session_factory, existing_run.id)

    assert run.status == initial_status
    assert run.finished_at == original_timestamp.replace(tzinfo=None)


def test_unknown_run(
    test_session_factory: sessionmaker[Session],
):
    timestamp = datetime(2032, 11, 11, 0, 0, tzinfo=UTC)
    message = make_message_run_status(
        UUID("00000000-0000-0000-0000-000000000001"), timestamp, "running"
    )

    with pytest.raises(UnknownRunError):
        asyncio.run(process_telemetry_message(message, test_session_factory))
