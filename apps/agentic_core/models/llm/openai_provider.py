import httpx

from agentic_core.models.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):
    """
    OpenAI Chat Completions client, implemented directly over ``httpx``
    (already a dependency of this repo) rather than pulling in the
    ``openai`` SDK as a new package dependency.

    Only used when ``OPENAI_API_KEY`` is actually set; see
    ``agentic_core.models.llm.factory.get_llm_provider``.
    """

    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )

        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
