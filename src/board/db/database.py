from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_DIR = PROJECT_ROOT / "data"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATABASE_DIR / 'training_monitor.db'}"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}, echo=True
)

SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
