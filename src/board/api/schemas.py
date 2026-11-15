from datetime import datetime
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import ConfigDict, Field

from board.telemetry.protocol import StrictModel


class ExperimentRequest(StrictModel):
    """
    Schema for Experiment requests

    POST /api/v1/experiments
    """

    name: str = Field(min_length=1, max_length=30)
    description: str | None = None


class ExperimentResponse(StrictModel):
    """Schema for Experiment response returned by API"""

    # To be able to export variables from ORM
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: int  # Created by DB
    name: str
    description: str | None
    created_at: (
        datetime  # Created by DB. SQLite doesn't support timezone-aware datetimes :(
    )


Status = Literal["pending", "running", "completed", "failed"]


class RunRequest(StrictModel):
    """
    Schema for Run requests

    POST /api/v1/experiments/{experiment_id}/runs
    """

    name: str = Field(min_length=1, max_length=128)
    model_name: str = Field(min_length=1, max_length=128)


class RunResponse(StrictModel):
    """Schema for Run response returned by API"""

    # To be able to export variables from ORM
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: UUID  # Created by DB
    experiment_id: int  # Mapped by DB
    name: str
    model_name: str
    status: Status  # Created by DB
    created_at: datetime  # Created by DB. Not timezone-aware
