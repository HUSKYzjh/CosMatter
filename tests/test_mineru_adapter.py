import json
import unittest
from unittest.mock import patch

from cosmatter.config import Settings
from cosmatter.mineru import MinerUAdapter, validate_remote_source_url


class FakeResponse:
    status = 200
    headers = {"x-request-id": "mineru-request-test"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return json.dumps({"code": 0, "data": {"task_id": "task_1", "state": "pending"}}).encode("utf-8")


class MinerUAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings.load(
            {
                "MINERU_API_TOKEN": "test-token",
                "MINERU_BASE_URL": "https://mineru.example",
                "MINERU_MODEL_VERSION": "vlm",
                "API_MAX_RETRIES": "1",
            }
        )

    def test_submit_uses_v4_task_endpoint_and_never_returns_source_content(self) -> None:
        with patch("cosmatter.mineru.urlopen", return_value=FakeResponse()) as mocked:
            task = MinerUAdapter(self.settings, sleep=lambda _: None).submit_remote_source("https://publisher.example/paper.pdf")
        request = mocked.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/api/v4/extract/task"))
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"url": "https://publisher.example/paper.pdf", "model_version": "vlm"})
        self.assertEqual(task.task_id, "task_1")
        self.assertEqual(task.state, "pending")
        self.assertEqual(task.request_id, "mineru-request-test")
        self.assertEqual(task.status_code, 200)

    def test_poll_has_no_request_body(self) -> None:
        with patch("cosmatter.mineru.urlopen", return_value=FakeResponse()) as mocked:
            MinerUAdapter(self.settings, sleep=lambda _: None).get_task("task_1")
        request = mocked.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/api/v4/extract/task/task_1"))
        self.assertIsNone(request.data)

    def test_source_url_rejects_local_or_insecure_targets(self) -> None:
        for value in ("http://publisher.example/paper.pdf", "https://localhost/paper.pdf", "https://127.0.0.1/paper.pdf", "https://10.0.0.1/paper.pdf"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_remote_source_url(value)
