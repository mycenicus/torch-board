from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Column,
    ForeignKey,
    MetaData,
    Named,
    String,
    Table,
    TypedColumns,
)

from board.db.database import engine

metadata_obj = MetaData()


class experiment_cols(TypedColumns):
    # fmt: off
    id:          Named[int]        = Column(primary_key=True)
    name:        Named[str]        = Column(String(length=30), nullable=False)
    description: Named[str | None] = Column(nullable=True)
    created_at:  Named[datetime]   = Column(nullable=False)
    # fmt: on


experiment_table = Table("experiment", metadata_obj, experiment_cols)


class run_cols(TypedColumns):
    # fmt: off
    id:            Named[UUID]            = Column(primary_key=True)
    experiment_id: Named[int]             = Column(ForeignKey("experiment.id"))
    name:          Named[str]             = Column(nullable=False)
    model_name:    Named[str]             = Column(nullable=False)
    status:        Named[str]             = Column(nullable=False)
    created_at:    Named[datetime]        = Column(nullable=False)
    started_at:    Named[datetime | None] = Column(nullable=True)
    finished_at:   Named[datetime | None] = Column(nullable=True)
    # fmt: on


run_table = Table("run", metadata_obj, run_cols)

metadata_obj.create_all(engine)
