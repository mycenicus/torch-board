import logging

from board.telemetry.protocol import TelemetryMessage
from board.telemetry.schemas import parse_event_payload

logger = logging.getLogger(__name__)


async def process_telemetry_message(message: TelemetryMessage) -> None:
    """Process one validated telemetry message"""

    payload = parse_event_payload(message.event_type, message.payload)

    logger.info(
        "Received telemetry: event_type=%s machine_id=%s sequence=%s",
        message.event_type,
        message.source.machine_id,
        message.sequence,
    )

    # TODO: Processing
    logger.debug("Processed payload: %s", payload)
