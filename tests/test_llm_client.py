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


def test_client_posts_chat_completion_and_returns_content(mocked_urlopen):
    mocked_urlopen.return_value = _response('{"ok": true}')
    client = OpenAICompatibleClient("https://example.test/v1/", "test-key")

    result = client.evaluate(
        system_prompt="system", payload={"model": "test-model", "journal": {"text": "jurnal"}}, timeout=3
    )

    assert result == '{"ok": true}'
    request = mocked_urlopen.call_args.args[0]
    assert request.full_url == "https://example.test/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert request.get_header("Content-type") == "application/json"
    body = json.loads(request.data)
    assert body["model"] == "test-model"
    assert body["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": '{"model": "test-model", "journal": {"text": "jurnal"}}'},
    ]
    assert body["response_format"] == {"type": "json_object"}
    assert mocked_urlopen.call_args.kwargs["timeout"] == 3


def test_client_propagates_timeout(mocked_urlopen):
    mocked_urlopen.return_value = _response("{}")

    OpenAICompatibleClient("https://example.test/v1", "key").evaluate(
        system_prompt="system", payload={"model": "test"}, timeout=0.25
    )

    assert mocked_urlopen.call_args.kwargs["timeout"] == 0.25


def test_client_sanitizes_non_success_http_error(mocked_urlopen):
    mocked_urlopen.side_effect = HTTPError(
        "https://example.test", 403, "private provider details", {}, None
    )

    with pytest.raises(ProviderRequestError) as exc_info:
        OpenAICompatibleClient("https://example.test/v1", "secret-key").evaluate(
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
        OpenAICompatibleClient("https://example.test/v1", "secret-key").evaluate(
            system_prompt="system", payload={"journal": {"text": "private journal"}}, timeout=1
        )

    assert str(exc_info.value) == "Provider request failed or returned an invalid response"
    assert "secret-key" not in str(exc_info.value)
    assert "private journal" not in str(exc_info.value)


def test_client_sanitizes_timeout(mocked_urlopen):
    mocked_urlopen.side_effect = TimeoutError("secret-key private journal")

    with pytest.raises(ProviderRequestError) as exc_info:
        OpenAICompatibleClient("https://example.test/v1", "secret-key").evaluate(
            system_prompt="system", payload={"journal": {"text": "private journal"}}, timeout=1
        )

    assert str(exc_info.value) == "Provider request failed or returned an invalid response"
    assert "secret-key" not in str(exc_info.value)
    assert "private journal" not in str(exc_info.value)
