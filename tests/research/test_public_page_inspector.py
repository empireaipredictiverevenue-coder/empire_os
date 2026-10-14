"""No-network security contract for first-party public HTML evidence fetching."""
from __future__ import annotations

import socket
import unittest

from empire_os.research.public_page_inspector import (
    _pinned_http_get, inspect_public_html, resolve_public_ips,
)

BODY = (b"<html><head><title>Public buyer programme</title></head>"
        b"<body><h1>Publishers programme</h1><p>"
        + b"Learn about the publisher programme and commercial intake evidence. " * 3
        + b"</p></body></html>")


def resolver(host, port, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("1.1.1.1", port))]


class InspectorTests(unittest.TestCase):
    def test_ip_is_pinned_and_content_is_hashed(self):
        calls = []
        def getter(host, ip, port, path, *, https, timeout):
            calls.append((host, ip, port, path, https))
            return 200, {"content-type": "text/html; charset=utf-8"}, BODY

        result = inspect_public_html(
            "https://publisher.org/about?q=leads", resolver=resolver, fetcher=getter,
        )
        self.assertEqual(result["status"], "ORIGINAL_HTML_HEADINGS_INSPECTED")
        self.assertEqual(calls, [("publisher.org", "1.1.1.1", 443, "/about?q=leads", True)])
        self.assertFalse(result["claim_accuracy_verified"])
        self.assertEqual(len(result["content_sha256"]), 64)
        self.assertIn("Publishers programme", result["document_headings"])

    def test_mixed_dns_public_private_rejected_before_fetch(self):
        def hostile(host, port, **kwargs):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", port)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port)),
            ]
        result = inspect_public_html(
            "https://example.org/",
            resolver=hostile,
            fetcher=lambda *args, **kwargs: self.fail("never request mixed IP host"),
        )
        self.assertEqual(result["status"], "DNS_UNSAFE_OR_UNAVAILABLE")

    def test_redirects_are_not_followed(self):
        value = inspect_public_html(
            "https://example.org/",
            resolver=resolver,
            fetcher=lambda *args, **kwargs: (
                302, {"location": "http://169.254.169.254/latest/meta-data"}, b""
            ),
        )
        self.assertEqual(value["status"], "REDIRECT_NOT_FOLLOWED")

    def test_bad_content_rejected(self):
        for status, headers, body, expected in (
            (200, {"content-type": "application/json"}, BODY, "NON_HTML_REJECTED"),
            (200, {"content-type": "text/html", "content-encoding": "gzip"}, BODY, "COMPRESSED_CONTENT_REJECTED"),
            (200, {"content-type": "text/html"}, b"x" * 196_609, "CONTENT_SIZE_REJECTED"),
            (403, {"content-type": "text/html"}, BODY, "HTTP_NOT_SUCCESS"),
            (200, {"content-type": "text/html"}, b"<h1>NO</h1>", "PAGE_TOO_THIN"),
        ):
            with self.subTest(expected=expected):
                got = inspect_public_html(
                    "https://example.org/",
                    resolver=resolver,
                    fetcher=lambda *args, **kwargs: (status, headers, body),
                )
                self.assertEqual(got["status"], expected)

    def test_disallowed_url_no_fetch(self):
        self.assertEqual(
            inspect_public_html("http://127.0.0.1/a")["status"], "UNSAFE_URL_REJECTED"
        )
        self.assertEqual(
            inspect_public_html("https://example.org:8443", resolver=resolver)["status"],
            "UNSAFE_URL_REJECTED",
        )

    def test_network_failure_does_not_produce_evidence(self):
        def broken(*args, **kwargs):
            raise TimeoutError("read timed out")
        value = inspect_public_html(
            "https://example.org/", resolver=resolver, fetcher=broken,
        )
        self.assertEqual(value["status"], "NETWORK_OR_TLS_UNAVAILABLE")

    def test_public_resolver_rejects_reserved_ip(self):
        with self.assertRaises(ValueError):
            resolve_public_ips(
                "example.org", 443,
                resolver=lambda *args, **kwargs: [
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.10", 443))
                ],
            )


if __name__ == "__main__":
    unittest.main()
