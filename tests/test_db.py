from collections.abc import Generator

import pytest
from sqlalchemy import text

from board.db.database import SessionLocal, engine, get_db


@pytest.fixture
def db_create_test_table() -> Generator[None]:
    with engine.connect() as connection:
        connection.execute(text("CREATE TABLE test (x int, y int)"))
        connection.execute(
            text("INSERT INTO test (x, y) VALUES (:x, :y)"),
            [{"x": 1, "y": 1}, {"x": 2, "y": 4}],
        )
        connection.commit()

    try:
        yield
    finally:
        with engine.connect() as connection:
            connection.execute(text("DROP TABLE test"))
            connection.commit()


def test_engine_connection():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))

        assert result.scalar_one() == 1


def test_create_session():
    db = SessionLocal()

    assert db.bind == engine


def test_get_db():
    db = next(get_db())

    assert db.bind == engine
