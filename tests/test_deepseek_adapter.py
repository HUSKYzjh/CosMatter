import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from cosmatter.config import Settings
from cosmatter.deepseek import DeepSeekAdapter, DeepSeekRequestError


class FakeResponse:
    status = 200
    headers = {"x-request-id": "deepseek-fixture"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return json.dumps({"model": "deepseek-v4-flash", "choices": [{"message": {"content": "untrusted draft"}}]}).encode("utf-8")


class DeepSeekAdapterTests(unittest.TestCase):
    def test_draft_uses_bounded_nonstreaming_completion_request(self) -> None:
        settings = Settings.load(
            {
                "LLM_PROVIDER": "deepseek",
                "LLM_MODEL": "deepseek-v4-flash",
                "DEEPSEEK_API_KEY": "test-token",
                "LLM_THINKING_ENABLED": "true",
                "LLM_REASONING_EFFORT": "high",
                "API_MAX_RETRIES": "1",
            }
        )
        with patch("cosmatter.deepseek.urlopen", return_value=FakeResponse()) as mocked:
            completion = DeepSeekAdapter(settings, sleep=lambda _: None).draft(system_prompt="system", user_prompt="user")
        request = mocked.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))

        self.assertTrue(request.full_url.endswith("/chat/completions"))
        self.assertEqual(payload["stream"], False)
        self.assertEqual(payload["thinking"], {"type": "enabled"})
        self.assertEqual(payload["reasoning_effort"], "high")
        self.assertEqual(completion.content, "untrusted draft")

    def test_draft_can_bound_json_output(self) -> None:
        settings = Settings.load(
            {
                "LLM_PROVIDER": "deepseek",
                "LLM_MODEL": "deepseek-v4-flash",
                "DEEPSEEK_API_KEY": "test-token",
                "API_MAX_RETRIES": "1",
            }
        )
        with patch("cosmatter.deepseek.urlopen", return_value=FakeResponse()) as mocked:
            DeepSeekAdapter(settings, sleep=lambda _: None).draft(
                system_prompt="system", user_prompt="user", max_tokens=2500, json_object=True,
                thinking_enabled=False,
            )
        payload = json.loads(mocked.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["max_tokens"], 2500)
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["thinking"], {"type": "disabled"})

        with self.assertRaises(ValueError):
            DeepSeekAdapter(settings).draft(system_prompt="system", user_prompt="user", max_tokens=0)

    def test_transport_failure_uses_safe_reason_code(self) -> None:
        settings = Settings.load(
            {
                "LLM_PROVIDER": "deepseek",
                "LLM_MODEL": "deepseek-v4-flash",
                "DEEPSEEK_API_KEY": "test-token",
                "API_MAX_RETRIES": "1",
            }
        )
        with patch("cosmatter.deepseek.urlopen", side_effect=URLError("private endpoint detail")):
            with self.assertRaisesRegex(DeepSeekRequestError, "transport") as caught:
                DeepSeekAdapter(settings, sleep=lambda _: None).draft(system_prompt="system", user_prompt="user")
        self.assertNotIn("private endpoint detail", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
