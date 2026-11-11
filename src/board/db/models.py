from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from board.db.database import TelemetryBase, engine


class Experiment(TelemetryBase):
    __tablename__: str = "experiment"

    # fmt: off
    id:          Mapped[int] = mapped_column(primary_key=True)
    name:        Mapped[str] = mapped_column(String(length=30))
    description: Mapped[str | None]
    created_at:  Mapped[datetime]
    runs:        Mapped[list[Run]] = relationship(back_populates="experiment")
    # fmt: on


Status = Literal["pending", "running", "completed", "failed"]


class Run(TelemetryBase):
    __tablename__: str = "run"

    # fmt: off
    id:            Mapped[UUID] = mapped_column(primary_key=True)
    experiment_id: Mapped[int]  = mapped_column(ForeignKey("experiment.id"))
    name:          Mapped[str]
    model_name:    Mapped[str]
    status:        Mapped[Status]
    created_at:    Mapped[datetime]
    started_at:    Mapped[datetime | None]
    finished_at:   Mapped[datetime | None]
    experiment:    Mapped[Experiment] = relationship(back_populates="runs")
    # fmt: on


TelemetryBase.metadata.create_all(engine)
