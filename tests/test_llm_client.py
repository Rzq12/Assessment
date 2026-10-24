import json
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import pytest

from app.services.llm_client import OpenAICompatibleClient, ProviderRequestError


@pytest.fixture
def mocked_urlopen():
    with patch("app.services.llm_client.urlopen") as urlopen:
        yield urlopen


def _response(content):
    response = Mock()
    response.status = 200
    response.read.return_value = json.dumps(
        {"choices": [{"message": {"content": content}}]}
    ).encode("utf-8")
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    return response


def test_client_posts_only_standard_chat_fields(mocked_urlopen):
    mocked_urlopen.return_value = _response('{"ok": true}')
    client = OpenAICompatibleClient("https://example.test/v1/", "test-key", "test-model")

    result = client.evaluate(system_prompt="system", payload={"journal": {"text": "jurnal"}}, timeout=3)

    assert result == '{"ok": true}'
    request = mocked_urlopen.call_args.args[0]
    assert request.full_url == "https://example.test/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert request.get_header("Content-type") == "application/json"
    body = json.loads(request.data)
    assert set(body) == {"model", "temperature", "messages", "response_format"}
    assert body["model"] == "test-model"
    assert body["temperature"] == 0.0
    assert body["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": '{"journal": {"text": "jurnal"}}'},
    ]
    assert body["response_format"] == {"type": "json_object"}
    assert mocked_urlopen.call_args.kwargs["timeout"] == 3


def test_client_uses_configured_temperature(mocked_urlopen):
    mocked_urlopen.return_value = _response("{}")
    OpenAICompatibleClient("https://example.test/v1", "key", "m", temperature=0.2).evaluate(
        system_prompt="system", payload={}, timeout=1
    )
    assert json.loads(mocked_urlopen.call_args.args[0].data)["temperature"] == 0.2


def test_describe_image_sends_png_to_vision_model(mocked_urlopen):
    mocked_urlopen.return_value = _response("Diagram alur")
    client = OpenAICompatibleClient("https://example.test/v1", "key", "text-model", vision_model="vision-model")

    assert client.describe_image(prompt="Jelaskan", image_png=b"\x89PNG", timeout=2) == "Diagram alur"

    body = json.loads(mocked_urlopen.call_args.args[0].data)
    assert body["model"] == "vision-model"
    content = body["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "Jelaskan"}
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_client_propagates_timeout(mocked_urlopen):
    mocked_urlopen.return_value = _response("{}")

    OpenAICompatibleClient("https://example.test/v1", "key", "test-model").evaluate(
        system_prompt="system", payload={}, timeout=0.25
    )

    assert mocked_urlopen.call_args.kwargs["timeout"] == 0.25


def test_client_sanitizes_non_success_http_error(mocked_urlopen):
    mocked_urlopen.side_effect = HTTPError(
        "https://example.test", 403, "private provider details", {}, None
    )

    with pytest.raises(ProviderRequestError) as exc_info:
        OpenAICompatibleClient("https://example.test/v1", "secret-key", "test-model").evaluate(
            system_prompt="system", payload={"journal": {"text": "private journal"}}, timeout=1
        )

    assert str(exc_info.value) == "Provider request failed or returned an invalid response"
    assert "secret-key" not in str(exc_info.value)
    assert "private journal" not in str(exc_info.value)
    assert "private provider details" not in str(exc_info.value)


@pytest.mark.parametrize(
    "body",
    [b"not-json", b"{}", b'{"choices": []}', b'{"choices": [{"message": {}}]}', b'{"choices": [{"message": {"content": null}}]}'],
)
def test_client_sanitizes_malformed_provider_response(mocked_urlopen, body):
    response = Mock()
    response.status = 200
    response.read.return_value = body
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    mocked_urlopen.return_value = response

    with pytest.raises(ProviderRequestError) as exc_info:
        OpenAICompatibleClient("https://example.test/v1", "secret-key", "test-model").evaluate(
            system_prompt="system", payload={"journal": {"text": "private journal"}}, timeout=1
        )

    assert str(exc_info.value) == "Provider request failed or returned an invalid response"
    assert "secret-key" not in str(exc_info.value)
    assert "private journal" not in str(exc_info.value)


def test_client_sanitizes_timeout(mocked_urlopen):
    mocked_urlopen.side_effect = TimeoutError("secret-key private journal")

    with pytest.raises(ProviderRequestError) as exc_info:
        OpenAICompatibleClient("https://example.test/v1", "secret-key", "test-model").evaluate(
            system_prompt="system", payload={"journal": {"text": "private journal"}}, timeout=1
        )

    assert str(exc_info.value) == "Provider request failed or returned an invalid response"
    assert "secret-key" not in str(exc_info.value)
    assert "private journal" not in str(exc_info.value)
