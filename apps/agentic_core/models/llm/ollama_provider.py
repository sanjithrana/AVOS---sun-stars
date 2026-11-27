import httpx

from agentic_core.models.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    """
    Local Ollama server client (https://ollama.com), over its native
    ``/api/chat`` endpoint (non-streaming).

    Genuinely free and unlimited - it's your own machine, not a vendor
    quota - but requires Ollama installed and a model already pulled
    (``ollama pull llama3.1``) locally or reachable on your network. Only
    used when explicitly selected (see
    ``agentic_core.models.llm.factory.get_llm_provider``); nothing here
    tries to auto-detect whether Ollama is actually running.
    """

    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
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
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                )
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    f"Could not reach Ollama at {self.base_url}. Is "
                    f"`ollama serve` running, and has `ollama pull "
                    f"{self.model}` been run?"
                ) from exc

        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]
