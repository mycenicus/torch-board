import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
CLIENT_QUEUE_SIZE = 256


@dataclass(eq=False)
class WebSocketClient:
    websocket: WebSocket
    queue: asyncio.Queue[dict[str, object]] = field(
        default_factory=lambda: asyncio.Queue(maxsize=CLIENT_QUEUE_SIZE)
    )
    sender_task: asyncio.Task[None] | None = None


class WebSocketsManager:
    """
    Manager creates WebSocket async workers with a bounded queue

    For each run, spawns a new client that handles WebSocket messages
    """

    def __init__(self) -> None:
        self._clients: dict[UUID, set[WebSocketClient]] = defaultdict(set)

    async def connect(self, run_id: UUID, websocket: WebSocket) -> WebSocketClient:
        await websocket.accept()
        client = WebSocketClient(websocket=websocket)
        self._clients[run_id].add(client)
        client.sender_task = asyncio.create_task(self._send_loop(run_id, client))
        return client

    async def _send_loop(self, run_id: UUID, client: WebSocketClient) -> None:
        try:
            while True:
                message = await client.queue.get()
                try:
                    await client.websocket.send_json(message)
                finally:
                    client.queue.task_done()
        except WebSocketDisconnect, RuntimeError, OSError:
            logger.info("WebSocket client disconnected for run %s", run_id)
        finally:
            self._remove(run_id, client)

    def _remove(self, run_id: UUID, client: WebSocketClient) -> None:
        clients = self._clients.get(run_id)
        if clients is not None:
            clients.discard(client)
            if not clients:
                self._clients.pop(run_id, None)

    async def disconnect(self, run_id: UUID, client: WebSocketClient) -> None:
        self._remove(run_id, client)

        task = client.sender_task
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def publish_metric(self, run_id: UUID, metric: dict[str, object]) -> None:
        message: dict[str, object] = {
            "type": "metric_update",
            "run_id": str(run_id),
            "metric": metric,
        }

        # If queue fills, the manager disconnects so it can recconect and
        # recover over HTTP
        for client in tuple(self._clients.get(run_id, ())):
            try:
                client.queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning(
                    "Disconnecting slow WebSocket client for run: %s", run_id
                )
                await self.disconnect(run_id, client)

    async def close_all(self) -> None:
        clients = [
            (run_id, client)
            for run_id, run_clients in self._clients.items()
            for client in tuple(run_clients)
        ]
        for run_id, client in clients:
            try:
                await client.websocket.close(code=1001)
            except RuntimeError, WebSocketDisconnect:
                pass
            await self.disconnect(run_id, client)
