import httpx

async def send_telemetry(url, payload):
    if not url:
        return
    async with httpx.AsyncClient(timeout=3.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
