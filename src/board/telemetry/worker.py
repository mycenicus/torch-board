from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from board.telemetry.protocol import TelemetryMessage

logger = logging.getLogger(__name__)

MessageHandler = Callable[[TelemetryMessage], Awaitable[None]]


# TODO: multiple workers
class TelemetryWorker:
    """Bounded telemetry queue for processing messages"""

    def __init__(self, handler: MessageHandler, max_queue_size: int = 1000):
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be positive")

        self.queue: asyncio.Queue[TelemetryMessage] = asyncio.Queue(
            maxsize=max_queue_size
        )
        self.handler = handler
        self._task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _run(self) -> None:
        """Consume messages until the task is cancelled"""
        logger.info("Telemetry worker started")

        try:
            while True:
                message = await self.queue.get()

                try:
                    await self.handler(message)
                except Exception:
                    logger.exception(
                        f"Failed to process telemetry message {message.message_id}"
                    )
                finally:
                    self.queue.task_done()

        except asyncio.CancelledError:
            logger.info("Telemetry worker cancelled")
            raise

    def start(self) -> None:
        """Start the background worker"""
        if self.is_running:
            raise RuntimeError("Telemetry worker is already running")

        self._task = asyncio.create_task(self._run(), name="telemetry-worker")

    def submit(self, message: TelemetryMessage) -> None:
        """Add a message without waiting for queue capacity"""
        if not self.is_running:
            raise RuntimeError("Telemetry worker is not running")

        self.queue.put_nowait(message)

    async def stop(self, timeout: float = 10.0) -> None:
        """Drain pending messages, then stop the worker"""
        if self._task is None:
            return

        task = self._task

        try:
            await asyncio.wait_for(self.queue.join(), timeout=timeout)
        except TimeoutError:
            logger.warning(
                f"Telemetry queue did not drain within {timeout:.1f} seconds"
            )
        finally:
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            self._task = None

        logger.info("Telemetry worker stopped")
