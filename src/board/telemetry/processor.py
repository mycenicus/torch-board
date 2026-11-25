import logging

from sqlalchemy.orm import Session, sessionmaker

from board.api.schemas import MetricFloatResponse
from board.db.database import SessionLocal
from board.db.models import MetricFloat, Run
from board.telemetry.connections import WebSocketsManager
from board.telemetry.protocol import TelemetryMessage
from board.telemetry.schemas import MetricBatch, RunStatus, parse_event_payload

logger = logging.getLogger(__name__)


class UnknownRunError(Exception):
    """Raised when something is not found in DB"""


# This is rather a dispatcher to handlers
# FIXME: we want async processor, but DB engine is synchronous
async def process_telemetry_message(
    message: TelemetryMessage,
    session_factory: sessionmaker[Session] = SessionLocal,
    ws_connection_manager: WebSocketsManager | None = None,
) -> None:
    """Validate and persist one message asynchronously"""

    payload = parse_event_payload(message.event_type, message.payload)

    logger.info(
        "Received telemetry: event_type=%s machine_id=%s sequence=%s",
        message.event_type,
        message.source.machine_id,
        message.sequence,
    )

    # FIXME: all handlers are synchronous. Read above FIXME for why
    match message.event_type:
        case "metrics.batch":
            if not isinstance(payload, MetricBatch):
                raise TypeError("Unexpected payload type for metrics.batch")

            logger.info("Called handler for %s", message.event_type)

            records = handle_metrics_batch(session_factory, message, payload)

            if ws_connection_manager is not None:
                logger.info("WebSockets are now handling metrics")
                for record in records:
                    await ws_connection_manager.publish_metric(message.run_id, record)

        case "run.status":
            if not isinstance(payload, RunStatus):
                raise TypeError("Unexpected payload type for metrics.batch")

            logger.info("Called handler for %s", message.event_type)
            handle_run_status(session_factory, message, payload)

        case _:
            logger.info("Ignoring unsupported event: %s", message.event_type)


def handle_metrics_batch(
    session_factory: sessionmaker[Session],
    message: TelemetryMessage,
    payload: MetricBatch,
) -> list[dict[str, object]]:
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
        session.flush()

        records = [
            MetricFloatResponse.model_validate(metric).model_dump(mode="json")
            for metric in metrics
        ]

    logger.info(
        "Persisted %d metrics for run %s at step %d",
        len(payload.metrics),
        message.run_id,
        payload.step,
    )

    return records


def handle_run_status(
    session_factory: sessionmaker[Session],
    message: TelemetryMessage,
    payload: RunStatus,
) -> None:
    with session_factory.begin() as session:
        run = session.get(Run, message.run_id)

        if run is None:
            raise UnknownRunError(f"Run {message.run_id} does not exist")

        old_status = run.status

        if old_status in ("completed", "failed"):
            logger.debug(
                "Ignoring change of status for %s: status=%s",
                message.run_id,
                old_status,
            )
            return

        if payload.status == "running":
            if old_status == "pending":
                run.status = payload.status
                run.started_at = message.timestamp
        elif payload.status in ("completed", "failed"):
            run.status = payload.status
            run.finished_at = message.timestamp

    logger.debug(
        'Changed run status for %s: from "%s" to "%s"',
        message.run_id,
        old_status,
        payload.status,
    )
