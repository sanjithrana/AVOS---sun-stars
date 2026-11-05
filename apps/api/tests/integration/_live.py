"""Shared settings for tests that hit a *running* API (docker compose up).

    LIVE_API_URL=http://127.0.0.1:8001 pytest api/tests/integration

Skipped automatically when nothing answers GET /health at LIVE_API_URL.
"""

import os

import httpx
import pytest

API_URL = os.getenv("LIVE_API_URL", "http://127.0.0.1:8001")


def _api_up() -> bool:
    try:
        return httpx.get(f"{API_URL}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


requires_live_api = pytest.mark.skipif(not _api_up(), reason=f"No live API at {API_URL}")
