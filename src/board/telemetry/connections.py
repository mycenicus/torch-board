import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
CLIENT_QUEUE_SIZE = 256
CLIENT_CLEANUP_TIMEOUT = 0.5


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
        self._retiring: set[WebSocketClient] = set()
        self._background_tasks: set[asyncio.Task[None]] = set()

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
            await self.disconnect(run_id, client, close_code=1011)
        finally:
            self._remove(run_id, client)

    def _remove(self, run_id: UUID, client: WebSocketClient) -> None:
        clients = self._clients.get(run_id)
        if clients is not None:
            clients.discard(client)
            if not clients:
                self._clients.pop(run_id, None)

    def _track_task(self, task: asyncio.Task[None]) -> None:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _schedule_disconnect(
        self,
        run_id: UUID,
        client: WebSocketClient,
        *,
        close_code: int | None,
        reason: str | None = None,
    ) -> None:
        self._remove(run_id, client)
        self._retiring.add(client)

        # If client was sending a message, schedule it for cancel
        sender = client.sender_task
        if sender is not None and not sender.done():
            sender.cancel()
            self._track_task(sender)

        # The actual client cancel is a scheduled teardown
        teardown = asyncio.create_task(
            self._teardown_client(client, close_code=close_code, reason=reason)
        )
        self._track_task(teardown)

        def finish_retirement(_: asyncio.Task[None]) -> None:
            if teardown.done() and (sender is None or sender.done()):
                self._retiring.discard(client)

        teardown.add_done_callback(finish_retirement)
        if sender is not None:
            sender.add_done_callback(finish_retirement)

    async def _teardown_client(
        self, client: WebSocketClient, *, close_code: int | None, reason: str | None
    ) -> None:
        sender = client.sender_task
        if sender is not None and sender is not asyncio.current_task():
            sender.cancel()
            _, pending = await asyncio.wait({sender}, timeout=CLIENT_CLEANUP_TIMEOUT)
            if pending:
                logger.warning("WebSocket sender exceeded cleanup deadline")

        if close_code is None:
            return

        try:
            async with asyncio.timeout(CLIENT_CLEANUP_TIMEOUT):
                await client.websocket.close(code=close_code, reason=reason)
        except TimeoutError:
            logger.warning("WebSocket close exceeded cleanup deadline")
        except RuntimeError, WebSocketDisconnect, OSError:
            pass

    async def disconnect(
        self,
        run_id: UUID,
        client: WebSocketClient,
        *,
        close_code: int | None = None,
        reason: str | None = None,
    ) -> None:
        self._schedule_disconnect(run_id, client, close_code=close_code, reason=reason)

    async def publish_metric(self, run_id: UUID, metric: dict[str, object]) -> None:
        message: dict[str, object] = {
            "type": "metric_update",
            "run_id": str(run_id),
            "metric": metric,
        }

        # If the queue fills, close the client so it can reconnect and
        # recover over HTTP
        for client in tuple(self._clients.get(run_id, ())):
            try:
                client.queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning(
                    "Disconnecting slow WebSocket client for run: %s", run_id
                )
                self._schedule_disconnect(
                    run_id,
                    client,
                    close_code=1013,
                    reason="Client fell behind; reconnect to recover metrics.",
                )

        # put_nowait() doesn't suspend. Give sender tasks a chance to drain
        # their queues before the next metric is published.
        await asyncio.sleep(0)

    async def close_all(self) -> None:
        clients = [
            (run_id, client)
            for run_id, run_clients in self._clients.items()
            for client in tuple(run_clients)
        ]
        for run_id, client in clients:
            await self.disconnect(
                run_id,
                client,
                close_code=1001,
                reason="Server is shutting down.",
            )
