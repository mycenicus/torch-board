from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

PROTOCOL_VERSION = "0.1"


class StrictModel(BaseModel):
    """Base class for protocol models, each inherits from it"""

    model_config = ConfigDict(
        extra="forbid",  # Each new field should be introduced with new Protocol version
        frozen=True,
    )


class TelemetrySource(StrictModel):
    """Information about machine that produced telemetry"""

    machine_id: str = Field(min_length=1, max_length=128)
    hostname: str | None = None
    software_version: str | None = None


class TelemetryMessage(StrictModel):
    """
    Common class for all telemetry messages.

    Data lives in payload
    """

    protocol_version: Literal["0.1"] = PROTOCOL_VERSION

    message_id: UUID = Field(default_factory=uuid4)

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    source: TelemetrySource

    sequence: int = Field(ge=0)

    # Identifier
    event_type: str = Field(min_length=1, max_length=128)

    # Event specific JSON object
    # Its schema determined by event_type
    payload: dict[str, Any]

    # Optional extensions for payload, i.e. metadata
    extensions: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def timestamp_enforce_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value
