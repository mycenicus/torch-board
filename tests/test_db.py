from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from board.db.database import SessionLocal, engine, get_db


# FIXME: Creates in 'production' db for now
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

    try:
        assert db.bind == engine
    finally:
        db.close()


def test_get_db():
    db_generator = get_db()
    db = next(db_generator)

    try:
        assert db.bind == engine
    finally:
        db_generator.close()


def test_get_db_closes_session():
    """Test if Generator.close() is executed"""
    mock_session = MagicMock()

    with patch("board.db.database.SessionLocal", return_value=mock_session):
        db_generator = get_db()

        next(db_generator)

        mock_session.close.assert_not_called()

        db_generator.close()

        mock_session.close.assert_called_once()


def test_get_db_closes_session_after_exception():
    """Test if finally block executes in get_db"""
    mock_session = MagicMock()

    with patch("board.db.database.SessionLocal", return_value=mock_session):
        db_generator = get_db()

        next(db_generator)

        with pytest.raises(RuntimeError):
            db_generator.throw(RuntimeError("Something went wrong"))

        mock_session.close.assert_called_once()
