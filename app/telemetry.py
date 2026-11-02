import asyncio
import logging

import httpx

log = logging.getLogger("mr-market-intelligence")


class Telemetry:
    """Non-blocking sender: events are queued and delivered in the background with retries."""

    def __init__(self, url, token, max_queue=100):
        self.url = url
        self.token = token
        self.queue = asyncio.Queue(maxsize=max_queue)

    def submit(self, event):
        if not self.url:
            return
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            log.warning("Telemetry queue full; dropping event")

    async def run(self):
        if not self.url:
            return
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        async with httpx.AsyncClient(timeout=5.0) as client:
            while True:
                event = await self.queue.get()
                for attempt in range(3):
                    try:
                        response = await client.post(self.url, json=event, headers=headers)
                        response.raise_for_status()
                        break
                    except Exception as exc:
                        log.warning("Telemetry attempt %d failed: %s", attempt + 1, type(exc).__name__)
                        await asyncio.sleep(1 + attempt)
                else:
                    log.error("Telemetry event dropped after 3 attempts")
