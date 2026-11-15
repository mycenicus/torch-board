import asyncio
from collections.abc import Generator
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


def make_message(run_id: UUID) -> TelemetryMessage:
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


def test_persists_multiple_metrics(
    test_session_factory: sessionmaker[Session], existing_run: Run
):
    message = make_message(existing_run.id)

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


def test_unknown_run_is_not_persisted(test_session_factory: sessionmaker[Session]):
    message = make_message(uuid4())

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

    message = make_message(run2_id)

    asyncio.run(process_telemetry_message(message, test_session_factory))

    with test_session_factory() as session:
        metrics = session.scalars(select(MetricFloat)).all()

        assert len(metrics) == 2
        assert all(metric.run_id == run2_id for metric in metrics)
        assert all(metric.run_id != run1_id for metric in metrics)
