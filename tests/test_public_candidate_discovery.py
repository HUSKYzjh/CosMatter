import unittest
from email.message import Message
import socket
from urllib.error import HTTPError
from unittest.mock import patch
from cosmatter.public_candidate_discovery import PublicDiscoveryError, _connect_public_tcp, _resolve_public_tcp_addresses, discover_arxiv_candidates, discovery_receipt, probe_public_pdf, validate_redirect_chain, validate_public_url
class PublicDiscoveryTests(unittest.TestCase):
    def test_allows_public_allowlisted_chain_and_redacts_url(self):
        receipt = discovery_receipt(query="phase stability", redirect_chain=["https://doi.org/10.1/x", "https://arxiv.org/abs/1"], status_code=200, candidate_count=1)
        self.assertEqual(receipt["final_host"], "arxiv.org")
        self.assertNotIn("https://", str(receipt))

    def test_rejects_private_unknown_and_loop_redirects(self):
        for url in ("http://arxiv.org/a", "https://localhost/a", "https://127.0.0.1/a", "https://evil.example/a"):
            with self.assertRaises(PublicDiscoveryError):
                validate_public_url(url)
        with self.assertRaises(PublicDiscoveryError):
            validate_redirect_chain(["https://arxiv.org/a", "https://arxiv.org/a"])

    def test_policy_allows_only_the_reviewed_nature_host(self):
        self.assertEqual(
            validate_public_url("https://www.nature.com/articles/example.pdf"),
            "https://www.nature.com/articles/example.pdf",
        )
        for url in ("https://nature.com/articles/example.pdf", "https://nature.example/articles/example.pdf"):
            with self.assertRaises(PublicDiscoveryError):
                validate_public_url(url)

    def test_probe_requires_pdf_signature_or_media_type_and_redacts_url(self):
        class Response:
            status = 206
            headers = {"Content-Type": "application/pdf"}

            def read(self, _):
                return b"%PDF-"

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        class Opener:
            def open(self, *_, **__):
                return Response()

        with patch("cosmatter.public_candidate_discovery.build_opener", return_value=Opener()):
            receipt = probe_public_pdf("https://arxiv.org/pdf/1")
        self.assertEqual(receipt["final_host"], "arxiv.org")
        self.assertNotIn("https://", str(receipt))
        self.assertTrue(receipt["pdf_signature_confirmed"])

    def test_arxiv_discovery_returns_metadata_cards_without_atom_body_or_urls(self):
        atom = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/0909.4979v1</id><published>2010-01-01T00:00:00Z</published><title> Strain induced BiFeO3 phase transition </title><summary>must not persist</summary></entry></feed>'''

        class Response:
            status = 200

            def read(self, _):
                return atom

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        class Opener:
            def open(self, *_, **__):
                return Response()

        with patch("cosmatter.public_candidate_discovery.build_opener", return_value=Opener()):
            candidates, receipt = discover_arxiv_candidates("BiFeO3 strain", top_k=3)
        self.assertEqual(candidates, [{"document_id": "arxiv:0909.4979v1", "title": "Strain induced BiFeO3 phase transition", "query": "BiFeO3 strain", "source": "PublicArXiv", "publication_year": 2010, "is_content_accessible": False}])
        self.assertNotIn("summary", str(candidates))
        self.assertNotIn("https://", str(candidates) + str(receipt))

    def test_arxiv_discovery_follows_only_an_allowlisted_redirect_at_transport_time(self):
        atom = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/0909.4979v1</id><published>2010-01-01T00:00:00Z</published><title> Safe redirect result </title></entry></feed>'''
        headers = Message()
        headers["Location"] = "https://arxiv.org/api/query?redirected=1"

        class Response:
            status = 200

            def read(self, _):
                return atom

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        class Opener:
            def __init__(self):
                self.calls = 0

            def open(self, *_args, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise HTTPError("https://export.arxiv.org/api/query", 302, "redirect", headers, None)
                return Response()

        opener = Opener()
        with patch("cosmatter.public_candidate_discovery.build_opener", return_value=opener):
            candidates, receipt = discover_arxiv_candidates("BiFeO3 strain", top_k=1)
        self.assertEqual(opener.calls, 2)
        self.assertEqual(candidates[0]["document_id"], "arxiv:0909.4979v1")
        self.assertEqual(receipt["redirect_count"], 1)
        self.assertEqual(receipt["final_host"], "arxiv.org")
        self.assertNotIn("https://", str(candidates) + str(receipt))

    def test_arxiv_discovery_rejects_redirect_to_non_allowlisted_host_before_request(self):
        headers = Message()
        headers["Location"] = "https://evil.example/should-not-be-requested"

        class Opener:
            def __init__(self):
                self.calls = 0

            def open(self, *_args, **_kwargs):
                self.calls += 1
                raise HTTPError("https://export.arxiv.org/api/query", 302, "redirect", headers, None)

        opener = Opener()
        with patch("cosmatter.public_candidate_discovery.build_opener", return_value=opener):
            with self.assertRaises(PublicDiscoveryError):
                discover_arxiv_candidates("BiFeO3 strain", top_k=1)
        self.assertEqual(opener.calls, 1)

    def test_dns_resolution_rejects_non_public_address_and_keeps_public_endpoint(self):
        with patch("cosmatter.public_candidate_discovery.socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(PublicDiscoveryError):
                _resolve_public_tcp_addresses("arxiv.org", 443)
        with patch("cosmatter.public_candidate_discovery.socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("151.101.67.42", 443))]):
            self.assertEqual(
                _resolve_public_tcp_addresses("arxiv.org", 443),
                [(socket.AF_INET, socket.SOCK_STREAM, 6, ("151.101.67.42", 443))],
            )

    def test_tcp_connection_uses_the_checked_address_without_a_second_lookup(self):
        class CheckedSocket:
            def __init__(self):
                self.connected_to = None

            def settimeout(self, _):
                pass

            def setsockopt(self, *_):
                pass

            def connect(self, address):
                self.connected_to = address

            def close(self):
                self.fail("the checked public connection must remain open")

        checked_socket = CheckedSocket()
        record = (socket.AF_INET, socket.SOCK_STREAM, 6, ("151.101.67.42", 443))
        with patch("cosmatter.public_candidate_discovery._resolve_public_tcp_addresses", return_value=[record]) as resolver, patch("cosmatter.public_candidate_discovery.socket.socket", return_value=checked_socket) as new_socket:
            result = _connect_public_tcp("arxiv.org", 443, 10.0, None)
        self.assertIs(result, checked_socket)
        resolver.assert_called_once_with("arxiv.org", 443)
        new_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM, 6)
        self.assertEqual(checked_socket.connected_to, ("151.101.67.42", 443))
