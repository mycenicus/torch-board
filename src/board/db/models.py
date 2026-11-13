from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String
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
    id:            Mapped[UUID]   = mapped_column(primary_key=True, default=uuid4)
    experiment_id: Mapped[int]    = mapped_column(ForeignKey("experiment.id"))
    name:          Mapped[str]
    model_name:    Mapped[str]
    status:        Mapped[Status] = mapped_column(
                                        Enum(
                                            "pending",
                                            "running",
                                            "completed",
                                            "failed",
                                            native_enum=False,
                                            create_constraint=True,
                                            name="run_status",
                                        ),
                                        default="pending"
                                    )
    created_at:    Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    started_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    experiment:    Mapped[Experiment]      = relationship(back_populates = "runs")
    metrics:       Mapped[list[MetricFloat]] = relationship(back_populates="run")
    # fmt: on


class MetricFloat(TelemetryBase):
    """A row in a Run holding loss value, lr value or some other metric"""

    __tablename__: str = "metric"

    # fmt: off
    id:          Mapped[int]      = mapped_column(primary_key=True)
    run:         Mapped[Run]      = relationship(back_populates="metrics")
    run_id:      Mapped[UUID]     = mapped_column(ForeignKey("run.id"))
    name:        Mapped[str]      = mapped_column(CheckConstraint("length(name) > 0", name="name_not_empty")) # loss, lr, etc.
    value:       Mapped[float]
    step:        Mapped[int]      = mapped_column(CheckConstraint("step >= 0", name="step_positive"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default = lambda: datetime.now(UTC))
    # fmt: off
