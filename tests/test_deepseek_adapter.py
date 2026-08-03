import json
import unittest
from unittest.mock import patch

from cosmatter.config import Settings
from cosmatter.deepseek import DeepSeekAdapter


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


if __name__ == "__main__":
    unittest.main()
