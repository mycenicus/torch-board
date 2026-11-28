import os
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import QueuePool

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_DIR = PROJECT_ROOT / "data"
DEFAULT_DATABASE_URL = f"sqlite:///{DATABASE_DIR / 'training_monitor.db'}"


DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
parsed_url = make_url(DATABASE_URL)
IS_IN_MEMORY_DB = parsed_url.get_backend_name() == "sqlite" and parsed_url.database in (
    None,
    ":memory:",
)
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
