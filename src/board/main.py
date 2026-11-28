import asyncio
import logging
from contextlib import asynccontextmanager
from functools import partial
from typing import Annotated
from uuid import UUID

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from board.api.schemas import (
    ExperimentRequest,
    ExperimentResponse,
    MetricFloatResponse,
    RunRequest,
    RunResponse,
)
from board.db.database import IS_IN_MEMORY_DB, SessionLocal, get_db
from board.db.models import Experiment, MetricFloat, Run
from board.telemetry.connections import WebSocketsManager
from board.telemetry.processor import process_telemetry_message
from board.telemetry.protocol import TelemetryMessage
from board.telemetry.schemas import parse_event_payload
from board.telemetry.worker import TelemetryWorker

logger = logging.getLogger(__name__)

QUEUE_MAX_SIZE = 1000


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the telemetry worker lifecycle"""
    database_keepalive = None

    if IS_IN_MEMORY_DB:
        from board.db.database import TelemetryBase, engine

        database_keepalive = engine.connect()
        try:
            TelemetryBase.metadata.create_all(engine)
        except Exception:
            database_keepalive.close()
            raise

    session_factory = getattr(app.state, "session_factory", SessionLocal)
    ws_connection_manager = WebSocketsManager()
    app.state.ws_connection_manager = ws_connection_manager

    worker = TelemetryWorker(
        handler=partial(  # DB Session is partially applied
            process_telemetry_message,
            session_factory=session_factory,
            ws_connection_manager=ws_connection_manager,
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
        await ws_connection_manager.close_all()
        if database_keepalive is not None:
            database_keepalive.close()
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

    return {"status": "accepted", "message_id": str(message.message_id)}


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
    with session.begin():
        experiment = session.get(Experiment, experiment_id)

        if experiment is None:  # this exception will rollback transaction
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Experiment {experiment_id} not found",
            )

        run = Run(
            experiment=experiment, name=request.name, model_name=request.model_name
        )

        session.add(run)

    return run


@app.get("/api/v1/experiments", response_model=list[ExperimentResponse])
def get_experiments(session: SessionDep) -> list[Experiment]:
    statement = select(Experiment).order_by(Experiment.created_at.desc())
    return list(session.scalars(statement).all())


@app.get("/api/v1/experiments/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(experiment_id: int, session: SessionDep) -> Experiment:
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found"
        )
    return experiment


@app.get("/api/v1/experiments/{experiment_id}/runs", response_model=list[RunResponse])
def get_experiment_runs(experiment_id: int, session: SessionDep) -> list[Run]:
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found",
        )

    statement = (
        select(Run)
        .where(Run.experiment_id == experiment_id)
        .order_by(Run.created_at.desc())
    )
    return list(session.scalars(statement).all())


@app.get("/api/v1/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: UUID, session: SessionDep) -> Run:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found"
        )
    return run


@app.get("/api/v1/runs/{run_id}/metrics", response_model=list[MetricFloatResponse])
def get_run_metrics(
    run_id: UUID,
    session: SessionDep,
    after_id: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> list[MetricFloat]:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found"
        )

    statement = select(MetricFloat).where(MetricFloat.run_id == run_id)

    if after_id is None:
        statement = statement.order_by(MetricFloat.step.asc(), MetricFloat.id.asc())
    else:
        statement = (
            statement.where(MetricFloat.id > after_id)
            .order_by(MetricFloat.id.asc())
            .limit(limit)
        )
    return list(session.scalars(statement).all())


@app.websocket("/ws/runs/{run_id}")
async def run_metrics_websocket(
    websocket: WebSocket, run_id: UUID, session: SessionDep
) -> None:
    # db session waits until endpoint closes, but websocket can exist all application lifespan
    run_exists = session.get(Run, run_id) is not None
    session.close()

    if not run_exists:
        await websocket.close(code=1008)
        return

    manager: WebSocketsManager = websocket.app.state.ws_connection_manager
    client = await manager.connect(run_id, websocket)
    if client is None:
        return

    try:
        # Waiting for client input lets Starlette report when it disconnects.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(run_id, client)
