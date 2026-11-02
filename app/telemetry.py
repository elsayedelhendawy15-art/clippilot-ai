import httpx


async def send_telemetry(url, token, payload):
    if not url:
        return
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
