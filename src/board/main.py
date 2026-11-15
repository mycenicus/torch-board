import asyncio
import logging
from contextlib import asynccontextmanager
from functools import partial
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from board.api.schemas import (
    ExperimentRequest,
    ExperimentResponse,
    RunRequest,
    RunResponse,
)
from board.db.database import SessionLocal, get_db
from board.db.models import Experiment, Run
from board.telemetry.processor import process_telemetry_message
from board.telemetry.protocol import TelemetryMessage
from board.telemetry.schemas import parse_event_payload
from board.telemetry.worker import TelemetryWorker

logger = logging.getLogger(__name__)

QUEUE_MAX_SIZE = 1000


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the telemetry worker lifecycle"""

    worker = TelemetryWorker(
        handler=partial(  # DB Session is partially applied
            process_telemetry_message,
            session_factory=SessionLocal,
        ),
        max_queue_size=QUEUE_MAX_SIZE,
    )

    app.state.telemetry_worker = worker
    worker.start()

    logger.info("Application started")

    try:
        yield
    finally:
        await worker.stop(timeout=10.0)
        logger.info("Application stopped")


SessionDep = Annotated[Session, Depends(get_db)]

app = FastAPI(lifespan=lifespan)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.post("/api/v1/telemetry", status_code=status.HTTP_202_ACCEPTED)
async def receive_telemetry(
    message: TelemetryMessage, request: Request
) -> dict[str, str]:
    """Validate and enqueue an incoming telemetry message"""

    try:
        parse_event_payload(message.event_type, message.payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid telemetry payload",
        ) from exc

    worker: TelemetryWorker = request.app.state.telemetry_worker

    try:
        worker.submit(message)
    except asyncio.QueueFull:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry queue is full. Retry later.",
            headers={"Retry-After": "1"},
        )
    except RuntimeError as exc:
        logger.error("Telemetry worker unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry processing is unavailable",
        ) from exc

    return {"status": "accepted", "message_id": message.message_id.hex}


@app.get("/api/v1/telemetry/status")
async def telemetry_status(request: Request):
    worker: TelemetryWorker = request.app.state.telemetry_worker

    return {
        "worker_running": worker.is_running,
        "queue_size": worker.queue.qsize(),
        "queue_capacity": worker.queue.maxsize,
        "queue_remaining_capacity": (worker.queue.maxsize - worker.queue.qsize()),
    }


@app.post(
    "/api/v1/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)  # TODO: async
def create_experiment(request: ExperimentRequest, session: SessionDep) -> Experiment:
    with session.begin():
        experiment = Experiment(name=request.name, description=request.description)
        session.add(experiment)

    return experiment


@app.post(
    "/api/v1/experiments/{experiment_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)  # TODO: async
def create_run(experiment_id: int, request: RunRequest, session: SessionDep) -> Run:
    experiment = session.get(Experiment, experiment_id)

    if experiment is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Experiment {experiment_id} not found"
        )

    run = Run(experiment=experiment, name=request.name, model_name=request.model_name)

    with session.begin():
        session.add(run)

    return run
