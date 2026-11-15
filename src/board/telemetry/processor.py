import logging

from sqlalchemy.orm import Session, sessionmaker

from board.db.database import SessionLocal
from board.db.models import MetricFloat, Run
from board.telemetry.protocol import TelemetryMessage
from board.telemetry.schemas import MetricBatch, parse_event_payload

logger = logging.getLogger(__name__)


class UnknownRunError(Exception):
    """Raised when something is not found in DB"""


async def process_telemetry_message(
    message: TelemetryMessage,
    session_factory: sessionmaker[Session] = SessionLocal,
) -> None:
    """Validate and persist one message asynchronously"""

    payload = parse_event_payload(message.event_type, message.payload)

    # TODO: more payloads
    if not isinstance(payload, MetricBatch):
        logger.info("Ignoring unsupported event: %s", message.event_type)
        return

    logger.info(
        "Received telemetry: event_type=%s machine_id=%s sequence=%s",
        message.event_type,
        message.source.machine_id,
        message.sequence,
    )

    # begins a transaction, so it's safe
    # commits on success, otherwise rollbacks
    # FIXME: this is a synchronous function in async method
    with session_factory.begin() as session:
        run = session.get(Run, message.run_id)

        if run is None:
            raise UnknownRunError(f"Run {message.run_id} does not exist")

        metrics = [
            MetricFloat(
                run=run,
                name=metric.name,
                value=metric.value,
                step=payload.step,
                recorded_at=message.timestamp,
            )
            for metric in payload.metrics
        ]

        session.add_all(metrics)

    logger.info(
        "Persisted %d metrics for run %s at step %d",
        len(payload.metrics),
        message.run_id,
        payload.step,
    )
