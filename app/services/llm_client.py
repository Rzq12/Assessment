import base64
import json
import math
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderRequestError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        temperature: float = 0.0,
        vision_model: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.vision_model = vision_model or model

    def evaluate(self, *, system_prompt: str, payload: dict[str, Any], timeout: float) -> str:
        # Only standard chat-completions fields go at the top level; the assessment data
        # travels inside the user message so strict providers do not reject the request.
        return self._chat(
            {
                "model": self.model,
                "temperature": self.temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "response_format": {"type": "json_object"},
            },
            timeout,
        )

    def describe_image(self, *, prompt: str, image_png: bytes, timeout: float) -> str:
        image_url = "data:image/png;base64," + base64.b64encode(image_png).decode("ascii")
        return self._chat(
            {
                "model": self.vision_model,
                "temperature": self.temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
            },
            timeout,
        )

    def _chat(self, request_payload: dict[str, Any], timeout: float) -> str:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ProviderRequestError("Provider request timeout must be finite and positive")
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                if not 200 <= response.status < 300:
                    raise ProviderRequestError("Provider returned an unsuccessful response")
                body = json.loads(response.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Invalid response content")
            return content
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError):
            raise ProviderRequestError("Provider request failed or returned an invalid response") from None
