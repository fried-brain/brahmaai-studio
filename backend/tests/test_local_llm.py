import json

import httpx
import pytest

from app.core.config import Settings
from app.services.local_llm import LocalLLMClient, LocalLLMError


def make_settings(**overrides):
    return Settings(_env_file=None, **overrides)


def test_local_llm_settings_have_safe_disabled_defaults():
    settings = make_settings()
    assert settings.local_llm_enabled is False
    assert settings.local_llm_base_url == "http://127.0.0.1:11434"
    assert settings.local_llm_model is None
    assert settings.local_llm_connect_timeout_seconds == 3.0
    assert settings.local_llm_read_timeout_seconds == 45.0


@pytest.mark.parametrize("url", ["ftp://localhost:11434", "file:///tmp/model", "http://user:pass@localhost:11434"])
def test_local_llm_rejects_unsafe_endpoint_urls(url):
    with pytest.raises(ValueError):
        make_settings(local_llm_base_url=url)


def test_status_reports_disabled_without_network_call():
    client = LocalLLMClient(make_settings())
    result = client.status()
    assert result.code == "disabled"
    assert result.enabled is False
    assert result.reachable is False


def test_status_reports_missing_model_without_network_call():
    client = LocalLLMClient(make_settings(local_llm_enabled=True))
    result = client.status()
    assert result.code == "model_not_configured"
    assert result.configured is False


def test_status_checks_configured_model_in_tags_response():
    def handler(request):
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    client = LocalLLMClient(make_settings(local_llm_enabled=True, local_llm_model="qwen2.5:7b"), http_client=http)
    result = client.status()
    assert result.code == "ready"
    assert result.reachable and result.model_available


def test_status_reports_configured_model_missing_from_runtime():
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"models": [{"name": "other"}]})))
    client = LocalLLMClient(make_settings(local_llm_enabled=True, local_llm_model="qwen2.5:7b"), http_client=http)
    assert client.status().code == "model_unavailable"


def test_chat_posts_json_mode_and_returns_model_text():
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert payload["stream"] is False
        assert payload["format"] == {"type": "object"}
        return httpx.Response(200, json={"message": {"content": '{"type":"answer"}'}})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = LocalLLMClient(make_settings(local_llm_enabled=True, local_llm_model="qwen2.5:7b"), http_client=http)
    result = client.chat([{"role": "user", "content": "hello"}], {"type": "object"})
    assert result.text == '{"type":"answer"}'
    assert result.model == "qwen2.5:7b"


@pytest.mark.parametrize("response", [
    httpx.Response(503, text="offline"),
    httpx.Response(200, text="not-json"),
    httpx.Response(200, content=b"x" * 128),
])
def test_status_handles_http_malformed_and_oversized_responses(response):
    http = httpx.Client(transport=httpx.MockTransport(lambda request: response))
    client = LocalLLMClient(make_settings(local_llm_enabled=True, local_llm_model="qwen2.5:7b", local_llm_max_response_bytes=64), http_client=http)
    result = client.status()
    assert result.code == "model_unavailable"
    assert "127.0.0.1" not in result.message


def test_chat_translates_connection_failure_to_typed_error():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = LocalLLMClient(make_settings(local_llm_enabled=True, local_llm_model="qwen2.5:7b"), http_client=http)
    with pytest.raises(LocalLLMError):
        client.chat([], {})


def test_status_translates_timeout_to_unavailable_without_leaking_endpoint():
    def handler(request):
        raise httpx.ReadTimeout("private endpoint timeout", request=request)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = LocalLLMClient(make_settings(local_llm_enabled=True, local_llm_model="qwen2.5:7b"), http_client=http)
    result = client.status()
    assert result.code == "model_unavailable"
    assert "127.0.0.1" not in result.message
    assert "private endpoint" not in result.message
