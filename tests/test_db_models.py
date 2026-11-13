from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from board.db.database import TelemetryBase, engine
from board.db.models import Experiment, MetricFloat, Run


@pytest.fixture
def db_session() -> Generator[Session]:
    # In-memory db
    test_engine = create_engine("sqlite:///:memory:")

    # SQLite does not enforce foreign keys by default.
    from sqlalchemy import event

    @event.listens_for(test_engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TelemetryBase.metadata.create_all(test_engine)

    TestSession = sessionmaker(bind=test_engine)

    try:
        with TestSession() as session:
            yield session
    finally:
        test_engine.dispose()


def test_check_dev_db_connectivity():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


def test_create_experiment(db_session: Session):
    experiment = Experiment(
        id=1, name="Test experiment", description="Cool description"
    )

    db_session.add(experiment)
    db_session.commit()

    assert experiment.id == 1
    assert experiment.name == "Test experiment"
    assert experiment.description == "Cool description"
    assert experiment.created_at is not None


def test_create_experiment_without_description(db_session: Session):
    """Checks if nullable works"""
    experiment = Experiment(id=2, name="Test experiment")

    db_session.add(experiment)
    db_session.commit()

    assert experiment.description is None


def test_create_experiment_without_id(db_session: Session):
    experiment = Experiment(name="Test experiment")

    db_session.add(experiment)
    db_session.flush()

    assert experiment.id is not None


def test_create_runs(db_session: Session):
    experiment = Experiment(id=1, name="Test experiment")
    db_session.add(experiment)
    db_session.flush()

    run = Run(
        experiment=experiment,
        experiment_id=experiment.id,
        name="First run",
        model_name="transformer",
    )

    db_session.add(run)
    db_session.commit()

    assert run.id is not None and hasattr(run.id, "hex")
    assert run.name == "First run"
    assert run.model_name == "transformer"
    assert run.status == "pending"
    assert run.created_at is not None and hasattr(run.created_at, "now")
    assert run.started_at is None
    assert run.finished_at is None
    assert run.experiment is experiment


def test_experiment_has_multiple_runs(db_session: Session):
    experiment = Experiment(id=1, name="Test experiment")

    experiment.runs = [
        Run(name="Run 1", model_name="transformer"),
        Run(name="Run 2", model_name="transformer"),
    ]

    db_session.add(experiment)
    db_session.commit()

    assert len(experiment.runs) == 2
    assert experiment.runs[0].experiment is experiment
    assert experiment.runs[0].experiment_id is experiment.id
    assert experiment.runs[1].experiment is experiment
    assert experiment.runs[1].experiment_id is experiment.id


def test_run_requires_existing_experiment(db_session: Session):
    run = Run(experiment_id=999, name="Test run", model_name="transformer")

    db_session.add(run)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_experiment_column_is_timezone_aware():
    column = Experiment.__table__.c.created_at

    assert column.type.timezone is True


def test_run_columns_are_timezone_aware():
    columns = Run.__table__.c

    assert columns.created_at.type.timezone is True
    assert columns.started_at.type.timezone is True
    assert columns.finished_at.type.timezone is True


def test_metricfloat_rejects_empty_name(db_session: Session):
    """Check CHECK length(name) > 0 constraint works"""
    experiment = Experiment(name="Test experiment")
    run = Run(name="Run 1", model_name="transformer")
    metric = MetricFloat(name="", value=0.42, step=0)

    experiment.runs.append(run)
    run.metrics.append(metric)

    db_session.add(experiment)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_metricfloat_rejects_negative_step(db_session: Session):
    """Check CHECK step >= 0 constraint works"""
    experiment = Experiment(name="Test experiment")
    run = Run(name="Run 1", model_name="transformer")
    metric = MetricFloat(name="loss", value=0.42, step=-1)

    experiment.runs.append(run)
    run.metrics.append(metric)

    db_session.add(experiment)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_create_multiple_metricfloat():
    """Test two-way relationships"""
    experiment = Experiment(name="Test experiment")
    run = Run(name="Run 1", model_name="transformer")
    metric1 = MetricFloat(name="loss", value=0.42, step=0)
    metric2 = MetricFloat(name="lr", value=0.001, step=0)

    experiment.runs.append(run)
    run.metrics.append(metric1)
    run.metrics.append(metric2)

    assert experiment.runs[0].metrics[0].name == "loss"
    assert experiment.runs[0].metrics[1].name == "lr"

    assert metric1.run.name == "Run 1"
    assert metric2.run.name == "Run 1"

    assert metric1.run.experiment.name == "Test experiment"
    assert metric2.run.experiment.name == "Test experiment"


def test_persistance(db_session: Session):
    """
    Test persistance and that sqlalchemy loads ORM correctly
    In particular we hope to see that relationships are persisted
    """
    experiment = Experiment(name="Test experiment")
    run = Run(name="Run 1", model_name="transformer")
    metric1 = MetricFloat(name="loss", value=0.42, step=0)
    metric2 = MetricFloat(name="lr", value=0.001, step=0)

    experiment.runs.append(run)
    run.metrics.append(metric1)
    run.metrics.append(metric2)

    db_session.add(experiment)
    db_session.commit()
    db_session.expire_all()

    loaded_run = db_session.query(Run).one()

    assert len(loaded_run.metrics) == 2

    assert loaded_run.metrics[0].name == "loss"
    assert loaded_run.metrics[1].name == "lr"
