"""In-process pub/sub for extraction SSE (D004).

One API process only — swap for Redis/NATS before horizontal scale.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class EventHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._latest: dict[str, dict[str, Any]] = {}

    async def subscribe(self, channel: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
        async with self._lock:
            self._subscribers[channel].add(queue)
            latest = self._latest.get(channel)
        if latest is not None:
            await queue.put(latest)
        return queue

    async def unsubscribe(self, channel: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subscribers[channel].discard(queue)
            if not self._subscribers[channel]:
                self._subscribers.pop(channel, None)

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        async with self._lock:
            self._latest[channel] = event
            subscribers = list(self._subscribers.get(channel, ()))
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    _ = queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass


extraction_hub = EventHub()


def extraction_channel(job_id: str) -> str:
    return f"extraction:{job_id}"
