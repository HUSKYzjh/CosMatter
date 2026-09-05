"""Bounded DeepSeek draft adapter; generated text never bypasses review gates."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings


class DeepSeekConfigurationError(RuntimeError):
    pass


class DeepSeekRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class DraftCompletion:
    content: str
    model: str
    request_id: str | None


class DeepSeekAdapter:
    """Narrow chat-completion client for producing explicitly untrusted drafts."""

    def __init__(self, settings: Settings, *, sleep=time.sleep) -> None:
        self.settings = settings
        self._sleep = sleep

    def draft(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        json_object: bool = False,
        thinking_enabled: bool | None = None,
    ) -> DraftCompletion:
        if not system_prompt.strip() or not user_prompt.strip():
            raise ValueError("system_prompt and user_prompt must be nonempty")
        if len(system_prompt) > 8_000 or len(user_prompt) > 20_000:
            raise ValueError("draft prompts exceed bounded input length")
        if max_tokens is not None and (isinstance(max_tokens, bool) or not 1 <= max_tokens <= 8_192):
            raise ValueError("draft max_tokens must be between 1 and 8192")
        if self.settings.llm_provider != "deepseek" or not self.settings.deepseek_api_key:
            raise DeepSeekConfigurationError("DeepSeek is not configured")
        if not self.settings.llm_model:
            raise DeepSeekConfigurationError("LLM_MODEL is required for DeepSeek")
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "stream": False,
        }
        effective_thinking = self.settings.llm_thinking_enabled if thinking_enabled is None else thinking_enabled
        if effective_thinking:
            payload["thinking"] = {"type": "enabled"}
        elif thinking_enabled is False:
            payload["thinking"] = {"type": "disabled"}
        if self.settings.llm_reasoning_effort and thinking_enabled is not False:
            payload["reasoning_effort"] = self.settings.llm_reasoning_effort
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if json_object:
            payload["response_format"] = {"type": "json_object"}
        return self._post_json("/chat/completions", payload)

    def _post_json(self, path: str, payload: dict[str, Any]) -> DraftCompletion:
        assert self.settings.deepseek_api_key is not None
        request = Request(
            url=f"{self.settings.llm_base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.settings.deepseek_api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self.settings.api_max_retries):
            try:
                with urlopen(request, timeout=self.settings.http_timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    content = _content_from_response(data)
                    return DraftCompletion(
                        content=content,
                        model=str(data.get("model", self.settings.llm_model)),
                        request_id=response.headers.get("x-request-id"),
                    )
            except HTTPError as error:
                last_error = error
                if error.code not in {429, 502, 503}:
                    raise DeepSeekRequestError(f"DeepSeek request failed with HTTP {error.code}") from error
            except DeepSeekRequestError:
                # A structurally invalid successful response is deterministic
                # for this payload; retrying it only repeats private content.
                raise
            except (URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
            if attempt + 1 < self.settings.api_max_retries:
                self._sleep(2**attempt)
        if isinstance(last_error, json.JSONDecodeError):
            reason = "invalid_json_response"
        elif isinstance(last_error, TimeoutError):
            reason = "timeout"
        elif isinstance(last_error, HTTPError):
            reason = f"http_{last_error.code}"
        else:
            reason = "transport"
        raise DeepSeekRequestError(f"DeepSeek request failed after configured retries: {reason}") from last_error


def _content_from_response(data: Any) -> str:
    if not isinstance(data, dict):
        raise DeepSeekRequestError("DeepSeek response was not a JSON object")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise DeepSeekRequestError("DeepSeek response did not contain a completion choice")
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise DeepSeekRequestError("DeepSeek response did not contain textual content")
    return content
