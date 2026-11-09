import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from board.telemetry.protocol import TelemetryMessage, TelemetrySource
from board.telemetry.schemas import MetricBatch, parse_event_payload


@pytest.fixture
def source():
    return TelemetrySource(
        machine_id="training-node-01",
        hostname="gpu-server-01",
        software_version="0.1.0",
    )


@pytest.fixture
def message_data(source):
    return {
        "source": source.model_dump(),
        "sequence": 1,
        "event_type": "metrics.batch",
        "payload": {
            "metrics": [
                {
                    "name": "loss",
                    "value": 0.42,
                    "unit": None,
                    "tags": {"split": "train"},
                }
            ]
        },
    }


def test_create_telemetry_message(message_data):
    message = TelemetryMessage.model_validate(message_data)

    assert message.protocol_version == "0.1"
    assert message.sequence == 1
    assert message.event_type == "metrics.batch"
    assert isinstance(message.message_id, UUID)


def test_is_frozen(message_data):
    message = TelemetryMessage.model_validate(message_data)

    with pytest.raises(ValidationError):
        message.sequence = 10  # pyrefly: ignore [read-only]


def test_message_id_is_generated(message_data):
    first = TelemetryMessage.model_validate(message_data)
    second = TelemetryMessage.model_validate(message_data)

    assert first.message_id != second.message_id


def test_timestamp_is_timezone_aware(message_data):
    message = TelemetryMessage.model_validate(message_data)

    assert message.timestamp.tzinfo is not None
    assert message.timestamp.utcoffset() is not None


def test_naive_timestamp_is_rejected(message_data):
    message_data["timestamp"] = "2026-11-09T12:00:00"

    with pytest.raises(ValidationError):
        TelemetryMessage.model_validate(message_data)


def test_negative_sequence_is_rejected(message_data):
    message_data["sequence"] = -1

    with pytest.raises(ValidationError):
        TelemetryMessage.model_validate(message_data)


def test_unknown_protocol_version_is_rejected(message_data):
    message_data["protocol_version"] = "2.0"

    with pytest.raises(ValidationError):
        TelemetryMessage.model_validate(message_data)


def test_strict_mode_unknown_field(message_data):
    message_data["unexpected"] = "value"

    with pytest.raises(ValidationError):
        TelemetryMessage.model_validate(message_data)


def test_json_serialize(message_data):
    original = TelemetryMessage.model_validate(message_data)

    serialized = original.model_dump_json()

    restored = TelemetryMessage.model_validate_json(serialized)

    assert restored == original


def test_serialized_message_is_valid_json(message_data):
    message = TelemetryMessage.model_validate(message_data)

    parsed = json.loads(message.model_dump_json())

    assert parsed["event_type"] == "metrics.batch"
    assert parsed["source"]["machine_id"] == "training-node-01"


def test_known_event_payload_is_validated():
    payload = {
        "metrics": [
            {
                "name": "loss",
                "value": 0.42,
                "unit": None,
                "tags": {},
            }
        ]
    }

    result = parse_event_payload("metrics.batch", payload)

    assert isinstance(result, MetricBatch)
    assert result.metrics[0].name == "loss"


def test_invalid_known_event_payload_is_rejected():
    payload = {"metrics": [{"value": 0.42}]}

    with pytest.raises(ValidationError):
        parse_event_payload("metrics.batch", payload)


def test_unknown_event_payload_is_preserved():
    payload = {
        "name": "future_event",
        "custom_data": [1, 2, 3],
    }

    result = parse_event_payload("future.custom", payload)

    assert result == payload
    assert isinstance(result, dict)


def test_extensions_are_supported(message_data):
    message_data["extensions"] = {"experiment_id": "experiment-001"}

    message = TelemetryMessage.model_validate(message_data)

    assert message.extensions["experiment_id"] == "experiment-001"
