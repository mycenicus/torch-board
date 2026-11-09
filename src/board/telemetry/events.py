from __future__ import annotations

from typing import Any

from pydantic import Field

from board.telemetry.protocol import StrictModel


class MetricSample(StrictModel):
    """A single scalar measurement"""

    name: str = Field(min_length=1, max_length=128)

    value: float

    unit: str | None = None

    # optional tags, e.g. {"device": "gpu0"}
    tags: dict[str, str] = Field(default_factory=dict)


class MetricBatch(StrictModel):
    """A batch of scalar measurements"""

    metrics: list[MetricSample] = Field(min_length=1)


# Assign event_type to Pydantic model
EVENT_SCHEMAS: dict[str, type[StrictModel]] = {
    "metrics.batch": MetricBatch,
}


def register_event(event_type: str, schema: type[StrictModel]) -> None:
    """Register a schema for an event type"""
    if not event_type:
        raise ValueError("event_type was not given")

    if event_type in EVENT_SCHEMAS:
        raise ValueError(f"event already registered: {event_type}")

    EVENT_SCHEMAS[event_type] = schema


def parse_event_payload(
    event_type: str, payload: dict[str, Any]
) -> StrictModel | dict[str, Any]:
    """
    Validate a known event payload.

    Unknown event types are return unchanged, allowing forward compatibility
    with event types not implemented by this server.
    """
    schema = EVENT_SCHEMAS.get(event_type)

    if schema is None:
        return payload

    return schema.model_validate(payload)
