"""OpenAI-compatible LLM client with streaming support."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from app.core.errors import LLMError

logger = logging.getLogger(__name__)


class LLMClient:
    """Async client for OpenAI-compatible chat-completion endpoints."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.2,
        max_tokens: int = 2048,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        self._headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        """Send a chat-completion request.

        Parameters
        ----------
        messages:
            OpenAI-style message list (``[{"role": ..., "content": ...}]``).
        stream:
            If ``True``, return an async iterator that yields content chunks.

        Returns
        -------
        str | AsyncIterator[str]
            Complete response text, or a streaming iterator.
        """
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }

        url = f"{self.base_url}/chat/completions"

        if stream:
            return self._stream(url, payload)

        return await self._request(url, payload)

    async def is_available(self) -> bool:
        """Return ``True`` if the LLM server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/models", headers=self._headers
                )
                return resp.status_code < 500
        except Exception:
            return False

    async def health_check(self) -> dict:
        """Return health/status information from the LLM server."""
        available = await self.is_available()
        return {
            "status": "ok" if available else "unavailable",
            "base_url": self.base_url,
            "model": self.model,
            "available": available,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _request(self, url: str, payload: dict) -> str:
        """Make a non-streaming request and return the assistant content."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url, json=payload, headers=self._headers
                )
        except httpx.ConnectError as exc:
            raise LLMError(
                message=f"Cannot connect to LLM server at {self.base_url}",
                details={"error": str(exc)},
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMError(
                message="LLM request timed out",
                details={"timeout": self.timeout, "error": str(exc)},
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(
                message="HTTP error communicating with LLM",
                details={"error": str(exc)},
            ) from exc

        if response.status_code == 401:
            raise LLMError(
                message="Authentication failed – check your API key",
                details={"status_code": 401},
            )
        if response.status_code == 404:
            raise LLMError(
                message=f"Model '{self.model}' not found",
                details={"status_code": 404, "model": self.model},
            )
        if response.status_code >= 400:
            raise LLMError(
                message=f"LLM API error (HTTP {response.status_code})",
                details={
                    "status_code": response.status_code,
                    "body": response.text[:500],
                },
            )

        try:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise LLMError(
                message="Unexpected response format from LLM",
                details={"body": response.text[:500]},
            ) from exc

    async def _stream(self, url: str, payload: dict) -> AsyncIterator[str]:
        """Return an async iterator that yields content deltas via SSE."""
        try:
            client = httpx.AsyncClient(timeout=self.timeout)
            response = await client.send(
                client.build_request("POST", url, json=payload, headers=self._headers),
                stream=True,
            )
        except httpx.ConnectError as exc:
            raise LLMError(
                message=f"Cannot connect to LLM server at {self.base_url}",
                details={"error": str(exc)},
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMError(
                message="LLM streaming request timed out",
                details={"timeout": self.timeout, "error": str(exc)},
            ) from exc

        if response.status_code >= 400:
            body = await response.aread()
            await response.aclose()
            await client.aclose()
            raise LLMError(
                message=f"LLM API error (HTTP {response.status_code})",
                details={"status_code": response.status_code, "body": body.decode()[:500]},
            )

        async def _iter() -> AsyncIterator[str]:
            try:
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[len("data: "):]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
            finally:
                await response.aclose()
                await client.aclose()

        return _iter()
