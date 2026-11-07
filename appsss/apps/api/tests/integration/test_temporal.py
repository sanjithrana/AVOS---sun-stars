import os

import httpx
import pytest

from tests.integration._live import API_URL, requires_live_api


pytestmark = requires_live_api


@pytest.mark.asyncio
async def test_temporal_hello_end_to_end() -> None:
    async with httpx.AsyncClient(
        base_url=API_URL,
        timeout=30.0,
    ) as client:
        response = await client.post(
            "/api/v1/internal/temporal/hello",
        )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Hello from solunex Temporal",
    }
