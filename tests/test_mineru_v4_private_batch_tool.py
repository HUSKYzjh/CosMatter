from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import mineru_v4_private_batch as command


class _Response:
    status = 204

    def __init__(self) -> None:
        self.read_called = False

    def read(self) -> bytes:
        self.read_called = True
        return b""


class _Connection:
    def __init__(self) -> None:
        self.request: tuple[object, ...] | None = None
        self.headers: list[tuple[str, str]] = []
        self.body: bytes | None = None
        self.response = _Response()
        self.closed = False

    def putrequest(self, *args: object, **kwargs: object) -> None:
        self.request = (*args, kwargs)

    def putheader(self, name: str, value: str) -> None:
        self.headers.append((name, value))

    def endheaders(self, body: bytes) -> None:
        self.body = body

    def getresponse(self) -> _Response:
        return self.response

    def close(self) -> None:
        self.closed = True


class MinerUV4PrivateBatchToolTests(unittest.TestCase):
    def test_signed_put_preserves_the_opaque_query_without_implicit_headers(self) -> None:
        connection = _Connection()
        settings = SimpleNamespace(http_timeout_seconds=17)
        with patch.object(command.http.client, "HTTPSConnection", return_value=connection) as constructor:
            status = command.signed_put(settings, "https://objects.example.test/upload/file?signature=opaque", b"pdf")

        self.assertEqual(status, 204)
        constructor.assert_called_once_with("objects.example.test", 443, timeout=17)
        self.assertEqual(connection.request, ("PUT", "/upload/file?signature=opaque", {"skip_accept_encoding": True}))
        self.assertEqual(connection.headers, [("Content-Length", "3")])
        self.assertEqual(connection.body, b"pdf")
        self.assertTrue(connection.response.read_called)
        self.assertTrue(connection.closed)

    def test_signed_put_rejects_non_https_targets_before_connecting(self) -> None:
        settings = SimpleNamespace(http_timeout_seconds=17)
        with patch.object(command.http.client, "HTTPSConnection") as constructor:
            self.assertEqual(command.signed_put(settings, "http://objects.example.test/upload", b"pdf"), 0)
            self.assertEqual(command.signed_put(settings, "https://user:secret@objects.example.test/upload", b"pdf"), 0)
            self.assertEqual(command.signed_put(settings, "https://objects.example.test/upload#fragment", b"pdf"), 0)
        constructor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
