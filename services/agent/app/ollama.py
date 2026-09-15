import asyncio
import base64
import json
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


class OllamaClient:
    def __init__(self, base_url: str, text_model: str, vision_model: str, timeout_seconds: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.text_model = text_model
        self.vision_model = vision_model
        self.timeout_seconds = timeout_seconds

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="GET" if body is None else "POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Ollama request failed: {error}") from error

    async def available_models(self) -> list[str]:
        response = await asyncio.to_thread(self._request, "/api/tags")
        return [model["name"] for model in response.get("models", []) if isinstance(model, dict) and "name" in model]

    async def answer(self, question: str, sql: str, rows: list[dict[str, Any]]) -> str:
        payload = {
            "model": self.text_model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": "Answer only from the supplied SQL result. Be concise. If the rows do not answer the question, say that the available data is insufficient.",
                },
                {
                    "role": "user",
                    "content": json.dumps({"question": question, "sql": sql, "rows": rows}, default=str),
                },
            ],
            "options": {"temperature": 0},
        }
        response = await asyncio.to_thread(self._request, "/api/chat", payload)
        content = response.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama returned no answer text")
        return content.strip()

    async def describe_image(self, image_path: Path) -> str:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        payload = {
            "model": self.vision_model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": "Describe only visible construction workers and PPE. Do not claim a violation when an item is hidden or uncertain.",
                    "images": [encoded],
                }
            ],
            "options": {"temperature": 0},
        }
        response = await asyncio.to_thread(self._request, "/api/chat", payload)
        content = response.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama returned no image description")
        return content.strip()
