from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings


class LocalLLMError(RuntimeError):
    """A safe, provider-independent local model gateway failure."""


@dataclass(frozen=True)
class LocalModelStatus:
    enabled: bool
    configured: bool
    reachable: bool
    model_available: bool
    code: str
    message: str


@dataclass(frozen=True)
class LocalModelReply:
    text: str
    model: str


class LocalLLMClient:
    def __init__(self, settings: Settings, http_client: httpx.Client | None = None):
        self.settings = settings
        timeout = httpx.Timeout(
            connect=settings.local_llm_connect_timeout_seconds,
            read=settings.local_llm_read_timeout_seconds,
            write=settings.local_llm_read_timeout_seconds,
            pool=settings.local_llm_connect_timeout_seconds,
        )
        self.http = http_client or httpx.Client(timeout=timeout)

    def _read_json(self, path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.settings.local_llm_base_url}{path}"
        try:
            with self.http.stream(method, url, json=payload) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    raise LocalLLMError("Local model service returned an unsuccessful response")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > self.settings.local_llm_max_response_bytes:
                        raise LocalLLMError("Local model response exceeded the configured size limit")
        except LocalLLMError:
            raise
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, httpx.HTTPError) as exc:
            raise LocalLLMError("Local model service is unavailable") from exc
        try:
            value = httpx.Response(200, content=bytes(body)).json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise LocalLLMError("Local model service returned malformed JSON") from exc
        if not isinstance(value, dict):
            raise LocalLLMError("Local model service returned an invalid response")
        return value

    def status(self) -> LocalModelStatus:
        if not self.settings.local_llm_enabled:
            return LocalModelStatus(False, bool(self.settings.local_llm_model), False, False, "disabled", "Local model integration is disabled")
        if not self.settings.local_llm_model:
            return LocalModelStatus(True, False, False, False, "model_not_configured", "No local model is configured")
        try:
            payload = self._read_json("/api/tags")
            models = payload.get("models", [])
            if not isinstance(models, list):
                raise LocalLLMError("Local model service returned an invalid model list")
            available_names = {
                str(item.get(key, ""))
                for item in models if isinstance(item, dict)
                for key in ("name", "model")
            }
            available = self.settings.local_llm_model in available_names
            return LocalModelStatus(True, True, True, available, "ready" if available else "model_unavailable", "Local model is ready" if available else "Configured model is not installed in the local runtime")
        except LocalLLMError:
            return LocalModelStatus(True, True, False, False, "model_unavailable", "Local model service is unavailable")

    def chat(self, messages: list[dict[str, str]], response_schema: dict[str, Any]) -> LocalModelReply:
        if not self.settings.local_llm_enabled or not self.settings.local_llm_model:
            raise LocalLLMError("Local model is not enabled and configured")
        payload = {
            "model": self.settings.local_llm_model,
            "messages": messages,
            "stream": False,
            "format": response_schema,
        }
        result = self._read_json("/api/chat", method="POST", payload=payload)
        message = result.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise LocalLLMError("Local model service returned no message content")
        return LocalModelReply(text=content, model=self.settings.local_llm_model)
