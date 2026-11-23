"""Unit tests for VLLMClient."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.llm.vllm_client import LLMError, VLLMClient


def test_vllm_client_successful_generation():
    client = VLLMClient(base_url="http://mock-llm:8000/v1")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Authentication is in app/auth.py."}}]
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value.post.return_value = mock_resp
        mock_client_cls.return_value = mock_ctx

        answer = client.generate("How does auth work?")
        assert answer == "Authentication is in app/auth.py."


def test_vllm_client_handles_connection_error():
    client = VLLMClient(base_url="http://invalid-host:8000/v1")

    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client_cls.return_value = mock_ctx

        with pytest.raises(LLMError) as exc_info:
            client.generate("Hello?")
        assert "Cannot connect to vLLM" in str(exc_info.value)


def test_vllm_client_ping():
    client = VLLMClient(base_url="http://mock-llm:8000/v1")

    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value.get.return_value.status_code = 200
        mock_client_cls.return_value = mock_ctx
        assert client.ping() is True

        mock_ctx.__enter__.return_value.get.side_effect = httpx.ConnectError("Failed")
        assert client.ping() is False
