"""Check if Alembic can correctly create, upgrade and recreate a db from scratch"""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import create_engine

from alembic import command

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


@pytest.fixture  # pytest creates tmp_path for every individual test
def alembic_config(tmp_path: Path) -> Config:
    """
    Create a test db on which we can test migrations

    pytest creates for every individual test a temporary directory, where we
    create a db on which we test migrations. Directory is deleted after the test
    See tmp_path fixture
    """
    database_path = tmp_path / "test_migrations.db"
    database_url = f"sqlite:///{database_path}"

    config = Config(str(ALEMBIC_INI))

    config.set_main_option(
        "sqlalchemy.url",
        database_url.replace("%", "%%"),  # escape for .ini files
    )

    return config


def get_table_names(config: Config) -> set[str]:
    """Return the names of tables in the test database"""
    url = config.get_main_option("sqlalchemy.url")

    if not url:
        raise RuntimeError("Database URL is not set in the config")

    engine = create_engine(url)

    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_fresh_db_gets_upgraded(alembic_config: Config):
    command.upgrade(alembic_config, "head")

    table_names = get_table_names(alembic_config)

    assert "experiment" in table_names
    assert "run" in table_names
    assert "alembic_version" in table_names


def test_upgrade_creates_correct_schema(alembic_config: Config):
    command.upgrade(alembic_config, "head")

    url = alembic_config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("Database URL is not set in the config")
    engine = create_engine(url)

    try:
        inspector = inspect(engine)

        # Check the Run primary key
        primary_key = inspector.get_pk_constraint("run")
        assert primary_key["constrained_columns"] == ["id"]

        # Check the Run foreign key
        foreign_keys = inspector.get_foreign_keys("run")

        assert any(
            fk["constrained_columns"] == ["experiment_id"]
            and fk["referred_table"] == "experiment"
            and fk["referred_columns"] == ["id"]
            for fk in foreign_keys
        )

        # Check the allowed Run statuses
        check_constraints = inspector.get_check_constraints("run")

        status_constraint = next(
            (
                constraint
                for constraint in check_constraints
                if constraint["name"] == "run_status"
            ),
            None,
        )
        assert status_constraint is not None

        expression = status_constraint["sqltext"]

        for status in ("pending", "running", "completed", "failed"):
            assert status in expression

    finally:
        engine.dispose()


def test_downgrade_removes_schema(alembic_config: Config):
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")

    table_names = get_table_names(alembic_config)

    assert "experiment" not in table_names
    assert "run" not in table_names


def test_upgrade_after_downgrade(alembic_config: Config):
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    table_names = get_table_names(alembic_config)

    assert "experiment" in table_names
    assert "run" in table_names


def test_no_pending_migrations(alembic_config: Config):
    command.upgrade(alembic_config, "head")

    # Fails if Alembic detects model changes not represented
    # in the existing migration files.
    command.check(alembic_config)
