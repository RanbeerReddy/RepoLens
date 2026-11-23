"""vLLM and OpenAI-compatible inference client."""

from __future__ import annotations

from typing import Optional

import httpx

from app.core.config import settings
from app.llm.prompts import SYSTEM_PROMPT


class LLMError(Exception):
    """Base exception for LLM inference failures."""


class VLLMClient:
    """Client for querying vLLM or any OpenAI-compatible completions endpoint."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        temperature: float = 0.1,
    ) -> None:
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self.api_key = api_key or settings.llm_api_key
        self.timeout = timeout
        self.temperature = temperature

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """Sends chat completion request to vLLM endpoint and returns generated response."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
        except (httpx.ConnectError, httpx.ConnectTimeout) as err:
            raise LLMError(f"Cannot connect to vLLM server at {self.base_url}: {err}") from err
        except httpx.HTTPStatusError as err:
            raise LLMError(f"vLLM server error (HTTP {err.response.status_code}): {err}") from err
        except Exception as err:
            raise LLMError(f"vLLM inference failure: {err}") from err

    def ping(self) -> bool:
        """Checks if the LLM inference server is reachable."""
        url = f"{self.base_url}/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(url, headers=headers)
                return res.status_code == 200
        except Exception:
            return False
