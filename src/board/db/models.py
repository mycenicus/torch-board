from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from board.db.database import TelemetryBase, engine


class Experiment(TelemetryBase):
    __tablename__: str = "experiment"

    # fmt: off
    id:          Mapped[int]       = mapped_column(primary_key=True)
    name:        Mapped[str]       = mapped_column(String(length=30))
    description: Mapped[str | None]
    created_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    runs:        Mapped[list[Run]] = relationship(back_populates="experiment")
    # fmt: on


Status = Literal["pending", "running", "completed", "failed"]


class Run(TelemetryBase):
    __tablename__: str = "run"

    # fmt: off
    id:            Mapped[UUID]            = mapped_column(primary_key=True, default=uuid4)
    experiment_id: Mapped[int]             = mapped_column(ForeignKey("experiment.id"))
    name:          Mapped[str]
    model_name:    Mapped[str]
    status:        Mapped[Status]          = mapped_column(default = "pending")
    created_at:    Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    started_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    experiment:    Mapped[Experiment]      = relationship(back_populates = "runs")
    # fmt: on


# TODO: temporary, remove when introducing Alembic integrations
TelemetryBase.metadata.create_all(engine)
