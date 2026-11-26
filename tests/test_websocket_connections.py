import asyncio
from typing import override
from uuid import uuid4

from board.telemetry.connections import CLIENT_QUEUE_SIZE, WebSocketsManager


class FakeWebSocket:
    def __init__(
        self,
        *,
        block_sends: bool = False,
        block_closes: bool = False,
        send_error: Exception | None = None,
    ) -> None:
        self.sent: list[dict[str, object]] = []
        self.closed: tuple[int, str | None] | None = None
        self.send_gate: asyncio.Event = asyncio.Event()
        self.close_gate: asyncio.Event = asyncio.Event()
        self.close_started: asyncio.Event = asyncio.Event()
        self.send_error: Exception | None = send_error
        if not block_sends:
            self.send_gate.set()
        if not block_closes:
            self.close_gate.set()

    async def accept(self) -> None:
        pass

    async def send_json(self, message: dict[str, object]) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.sent.append(message)
        await self.send_gate.wait()

    async def close(self, code: int, reason: str | None = None) -> None:
        self.close_started.set()
        await self.close_gate.wait()
        self.closed = (code, reason)


def test_sender_tasks_get_a_chance_to_drain_during_large_metric_batch():
    async def scenario() -> None:
        manager = WebSocketsManager()
        run_id = uuid4()
        websocket = FakeWebSocket()
        # pyrefly: ignore[bad-argument-type]
        client = await manager.connect(run_id, websocket)  # pyright: ignore[reportArgumentType]
        assert client is not None

        for metric_id in range(CLIENT_QUEUE_SIZE + 1):
            await manager.publish_metric(run_id, {"id": metric_id})

        await asyncio.sleep(0)

        assert len(websocket.sent) == CLIENT_QUEUE_SIZE + 1
        assert websocket.closed is None

        await manager.disconnect(run_id, client, close_code=1000)
        await manager.close_all()

    asyncio.run(scenario())


def test_queue_overflow_closes_and_unregisters_slow_client():
    async def scenario() -> None:
        manager = WebSocketsManager()
        run_id = uuid4()
        websocket = FakeWebSocket(block_sends=True)
        # pyrefly: ignore[bad-argument-type]
        await manager.connect(run_id, websocket)  # pyright: ignore[reportArgumentType]

        # One message is being sent; the remaining queue can hold 256.
        for metric_id in range(CLIENT_QUEUE_SIZE + 2):
            await manager.publish_metric(run_id, {"id": metric_id})

        await asyncio.wait_for(websocket.close_started.wait(), timeout=1)
        assert websocket.closed == (
            1013,
            "Client fell behind; reconnect to recover metrics.",
        )
        assert run_id not in manager._clients
        await manager.close_all()

    asyncio.run(scenario())


def test_publish_does_not_wait_for_a_slow_socket_close():
    async def scenario() -> None:
        manager = WebSocketsManager()
        run_id = uuid4()
        websocket = FakeWebSocket(block_sends=True, block_closes=True)
        # pyrefly: ignore[bad-argument-type]
        await manager.connect(run_id, websocket)  # pyright: ignore[reportArgumentType]

        for metric_id in range(CLIENT_QUEUE_SIZE + 2):
            await manager.publish_metric(run_id, {"id": metric_id})

        await asyncio.wait_for(websocket.close_started.wait(), timeout=1)
        assert websocket.closed is None
        assert run_id not in manager._clients

        websocket.close_gate.set()
        await manager.close_all()
        assert websocket.closed is not None

    asyncio.run(scenario())


def test_close_all_waits_for_retiring_client_teardown():
    async def scenario() -> None:
        manager = WebSocketsManager()
        run_id = uuid4()
        websocket = FakeWebSocket(block_closes=True)
        # pyrefly: ignore[bad-argument-type]
        client = await manager.connect(run_id, websocket)  # pyright: ignore[reportArgumentType]

        shutdown = asyncio.create_task(manager.close_all())
        await asyncio.wait_for(websocket.close_started.wait(), timeout=1)

        assert not shutdown.done()
        assert client in manager._retiring

        websocket.close_gate.set()
        await asyncio.wait_for(shutdown, timeout=1)

        assert websocket.closed == (1001, "Server is shutting down.")
        assert client not in manager._retiring

    asyncio.run(scenario())


def test_subscribers_receive_only_metrics_for_their_run():
    async def scenario() -> None:
        manager = WebSocketsManager()
        first_run_id = uuid4()
        second_run_id = uuid4()
        first_socket = FakeWebSocket()
        second_socket = FakeWebSocket()
        # pyrefly: ignore[bad-argument-type]
        await manager.connect(first_run_id, first_socket)  # pyright: ignore[reportArgumentType]
        # pyrefly: ignore[bad-argument-type]
        await manager.connect(second_run_id, second_socket)  # pyright: ignore[reportArgumentType]

        metric: dict[str, object] = {"id": 12, "name": "loss", "step": 4, "value": 0.25}
        await manager.publish_metric(first_run_id, metric)
        await asyncio.sleep(0)

        assert first_socket.sent == [
            {
                "type": "metric_update",
                "run_id": str(first_run_id),
                "metric": metric,
            }
        ]
        assert second_socket.sent == []
        await manager.close_all()

    asyncio.run(scenario())


def test_sender_failure_closes_socket_and_unregisters_client():
    async def scenario() -> None:
        manager = WebSocketsManager()
        run_id = uuid4()
        websocket = FakeWebSocket(send_error=ValueError("send failed"))
        # pyrefly: ignore[bad-argument-type]
        client = await manager.connect(run_id, websocket)  # pyright: ignore[reportArgumentType]
        assert client is not None

        await manager.publish_metric(run_id, {"id": 1})
        await asyncio.wait_for(websocket.close_started.wait(), timeout=1)

        # Retrieve an unexpected task exception so a missing error handler
        # produces this assertion failure rather than an unhandled-task warning.
        if client.sender_task is not None and client.sender_task.done():
            client.sender_task.exception()

        assert websocket.closed == (1011, None)
        assert run_id not in manager._clients
        await manager.close_all()

    asyncio.run(scenario())


# ------------------------ SHUTDOWN RACE TESTS --------------------------------


class AcceptBarrierWebSocket(FakeWebSocket):
    def __init__(self) -> None:
        super().__init__()
        self.accept_started: asyncio.Event = asyncio.Event()
        self.allow_accept: asyncio.Event = asyncio.Event()

    @override
    async def accept(self) -> None:
        self.accept_started.set()
        await self.allow_accept.wait()


def test_close_all_waits_for_in_progress_accept() -> None:
    async def scenario():
        manager = WebSocketsManager()
        run_id = uuid4()
        websocket = AcceptBarrierWebSocket()

        # pyrefly: ignore[bad-argument-type]
        connect_task = asyncio.create_task(manager.connect(run_id, websocket))  # pyright: ignore[reportArgumentType]
        await asyncio.wait_for(websocket.accept_started.wait(), timeout=1)

        close_task = asyncio.create_task(manager.close_all())
        await asyncio.sleep(0)

        assert not close_task.done()

        websocket.allow_accept.set()
        client = await asyncio.wait_for(connect_task, timeout=1)
        await asyncio.wait_for(close_task, timeout=1)

        assert client is not None
        assert client.disconnect_scheduled
        assert not manager._clients
        assert not manager._background_tasks

    asyncio.run(scenario())


def test_connect_is_rejected_after_close_all() -> None:
    async def scenario():
        manager = WebSocketsManager()
        await manager.close_all()

        websocket = AcceptBarrierWebSocket()
        # pyrefly: ignore[bad-argument-type]
        client = await manager.connect(uuid4(), websocket)  # pyright: ignore[reportArgumentType]

        assert client is None
        assert not websocket.accept_started.is_set()
        assert not manager._clients

    asyncio.run(scenario())
