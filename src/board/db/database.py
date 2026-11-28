import os
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import QueuePool


# Clanker discovered that uri=true is not the only possibility in sqlalchemy
# source.
# Other options are uri=t, uri=1, uri=y, ...
def _query_flag_is_true(value: str | tuple[str, ...] | None) -> bool:
    # Repeated query parameters are ambiguous; require exactly one value.
    if isinstance(value, tuple):
        if len(value) != 1:
            return False
        value = value[0]

    if not isinstance(value, str):
        return False

    return value.strip().casefold() in {"1", "true", "yes", "on", "y", "t"}


def is_in_memory_sqlite_url(database_url: str | URL) -> bool:
    url = make_url(database_url)

    if url.get_backend_name() != "sqlite":
        return False

    if url.database in (None, "", ":memory:"):
        return True

    is_sqlite_uri = url.database.startswith("file:") and _query_flag_is_true(
        url.query.get("uri")
    )
    is_memory_uri = url.query.get("mode") == "memory" or url.database.startswith(
        "file::memory:"
    )

    return is_sqlite_uri and is_memory_uri


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_DIR = PROJECT_ROOT / "data"
DEFAULT_DATABASE_URL = f"sqlite:///{DATABASE_DIR / 'training_monitor.db'}"


DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
IS_IN_MEMORY_DB = is_in_memory_sqlite_url(DATABASE_URL)
ENGINE_DATABASE_URL = DATABASE_URL


engine_options: dict[str, object] = {"echo": True}

if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

if IS_IN_MEMORY_DB:
    # Distinct DBAPI connections share the memory database but retain their
    # own transaction state. The app lifespan keeps the database alive.
    # Using UUID is required for multiple app instances.
    ENGINE_DATABASE_URL = (
        f"sqlite:///file:torch_board_{uuid4().hex}?mode=memory&cache=shared&uri=true"
    )
    engine_options["poolclass"] = QueuePool
else:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)


# TODO: async engine
engine = create_engine(ENGINE_DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(bind=engine)


class TelemetryBase(DeclarativeBase):
    pass


def get_db() -> Generator[Session]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
