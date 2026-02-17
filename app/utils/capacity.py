import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Awaitable, Callable, Any

@dataclass
class CapacitySnapshot:
    max_concurrent: int
    active: int
    queued: int
    max_queue: int
    started_at: float
    last_started_at: Optional[float]
    last_finished_at: Optional[float]
    total_started: int
    total_finished: int
    total_rejected: int

class CapacityManager:
    """Simple in-process concurrency limiter with bounded queue.

    This is intentionally lightweight for a single-container FastAPI deploy.
    It prevents 'all workers occupied' 503 storms by applying explicit backpressure.

    - If active < max_concurrent: start immediately
    - Else if queue < max_queue: optionally wait (FIFO) for a slot
    - Else: reject (503)

    Note: This is per-process. If you run multiple uvicorn workers, each has its own limits.
    """

    def __init__(self, max_concurrent: int = 1, max_queue: int = 10) -> None:
        self.max_concurrent = max(1, int(max_concurrent))
        self.max_queue = max(0, int(max_queue))
        self._active = 0
        self._queue: Deque[asyncio.Future] = deque()
        self._lock = asyncio.Lock()

        self._started_at = time.time()
        self._last_started_at: Optional[float] = None
        self._last_finished_at: Optional[float] = None
        self._total_started = 0
        self._total_finished = 0
        self._total_rejected = 0

    def snapshot(self) -> CapacitySnapshot:
        return CapacitySnapshot(
            max_concurrent=self.max_concurrent,
            active=self._active,
            queued=len(self._queue),
            max_queue=self.max_queue,
            started_at=self._started_at,
            last_started_at=self._last_started_at,
            last_finished_at=self._last_finished_at,
            total_started=self._total_started,
            total_finished=self._total_finished,
            total_rejected=self._total_rejected,
        )

    async def acquire(self, timeout_seconds: float = 0) -> bool:
        """Acquire a slot. Returns False if rejected."""
        timeout_seconds = float(timeout_seconds or 0)

        async with self._lock:
            if self._active < self.max_concurrent:
                self._active += 1
                self._total_started += 1
                self._last_started_at = time.time()
                return True

            if len(self._queue) >= self.max_queue:
                self._total_rejected += 1
                return False

            fut: asyncio.Future = asyncio.get_event_loop().create_future()
            self._queue.append(fut)

        try:
            if timeout_seconds > 0:
                await asyncio.wait_for(fut, timeout=timeout_seconds)
            else:
                # no waiting allowed -> immediate reject
                raise asyncio.TimeoutError()
        except asyncio.TimeoutError:
            async with self._lock:
                # remove from queue if still queued
                try:
                    self._queue.remove(fut)
                except ValueError:
                    pass
                self._total_rejected += 1
            return False

        # we were granted a slot
        async with self._lock:
            self._active += 1
            self._total_started += 1
            self._last_started_at = time.time()
        return True

    async def release(self) -> None:
        async with self._lock:
            self._active = max(0, self._active - 1)
            self._total_finished += 1
            self._last_finished_at = time.time()
            # wake next waiter (FIFO)
            while self._queue:
                fut = self._queue.popleft()
                if not fut.done():
                    fut.set_result(True)
                    break

    async def run(self, coro_fn: Callable[[], Awaitable[Any]], timeout_seconds: float = 0):
        ok = await self.acquire(timeout_seconds=timeout_seconds)
        if not ok:
            return None, False
        try:
            res = await coro_fn()
            return res, True
        finally:
            await self.release()
