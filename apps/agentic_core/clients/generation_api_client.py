from typing import Any

import httpx


class GenerationAPIError(RuntimeError):
    """Raised when the generation API rejects a request."""


class GenerationAPIClient:
    def __init__(
        self,
        base_url: str = "http://api:8000",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def generate(
        self,
        *,
        project_id: str,
        generation_type: str,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/projects/{project_id}/generate"

        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        ) as client:
            response = await client.post(
                url,
                json={
                    "generation_type": generation_type,
                },
            )

        if response.is_error:
            try:
                details = response.json()
            except ValueError:
                details = {"message": response.text}

            raise GenerationAPIError(
                f"Generation API returned HTTP {response.status_code}: "
                f"{details}"
            )

        return response.json()
