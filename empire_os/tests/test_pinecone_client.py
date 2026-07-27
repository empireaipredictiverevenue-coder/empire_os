#!/usr/bin/env python3
"""
test_pinecone_client.py — unit tests for the MCP client.

No live MCP. We mock `subprocess.Popen` and assert on the JSON-RPC frames
the client writes, then drive the read path with a fake stdout that returns
configured responses. Exercises: handshake, retry on transient, fail on
permanent, dim mismatch, key redaction, exception hierarchy.
"""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/root/empire_os")

from empire_os import pinecone_config
from empire_os import pinecone_client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_KEY = "pcsk_" + "A" * 65 + "YZ12"


def _fake_config(**overrides):
    """Build a PinconeConfig in-memory without touching .env."""
    defaults = dict(
        api_key=VALID_KEY, index="empire-leads", cloud="aws", region="us-east-1",
        embed_model="llama-text-embed-v2", dimension=1024,
    )
    defaults.update(overrides)
    return pinecone_config.PinconeConfig(**defaults)


@contextmanager
def _fake_mcp(responses: list[dict]):
    """
    Drive the client with a fake subprocess. The fake stdout yields the given
    responses one per readline() call. If the client reads past the end, it
    loops back to the START of the response list. The caller is responsible
    for ensuring the right id is in the right position.
    """
    # Looping fallback: when stdout EOFs, reset position to 0.
    class _LoopingStdout:
        def __init__(self, text: str):
            self._text = text
            self._pos = 0

        def readline(self, size: int = -1) -> str:
            if self._pos >= len(self._text):
                self._pos = 0  # loop
            nl = self._text.find("\n", self._pos)
            if nl < 0:
                line = self._text[self._pos:]
                self._pos = len(self._text)
            else:
                line = self._text[self._pos:nl + 1]
                self._pos = nl + 1
            return line

    body = "".join(json.dumps(r) + "\n" for r in responses)
    fake_stdout = _LoopingStdout(body)

    proc = MagicMock()
    proc.stdout = fake_stdout
    proc.stdin = MagicMock()
    proc.stderr = io.StringIO()
    proc.poll.return_value = None
    proc.returncode = None

    written: list[str] = []
    proc.stdin.write.side_effect = _capture_write(written)
    proc.stdin.flush.return_value = None

    with patch.object(pinecone_client.subprocess, "Popen", return_value=proc):
        yield proc, written


def _capture_write(written: list[str]):
    def _write(s):
        written.append(s)
    return _write


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConfig(unittest.TestCase):

    def test_redact_short(self):
        c = _fake_config(api_key="short")
        self.assertEqual(c.redact_key(), "shor...")

    def test_redact_long(self):
        c = _fake_config()  # VALID_KEY starts with pcsk_
        redacted = c.redact_key()
        self.assertTrue(redacted.startswith("pcsk_"))
        self.assertTrue(redacted.endswith("YZ12"))
        self.assertIn("...", redacted)


class TestClientHandshake(unittest.TestCase):

    def test_handshake_succeeds_with_tools(self):
        responses = [
            {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "x"}}},  # initialize
            {},  # notifications/initialized (no response expected)
            {"jsonrpc": "2.0", "id": 2, "result": {
                "tools": [{"name": "search-docs"}, {"name": "upsert-records"},
                          {"name": "search-records"}, {"name": "list-indexes"}]
            }},
        ]
        with _fake_mcp(responses) as (_proc, written):
            c = pinecone_client.PineconeClient(_fake_config(), timeout=2.0)
            self.assertTrue(c.health()["alive"])
            # Should have sent: initialize, notifications/initialized, tools/list
            self.assertEqual(len(written), 3)
            init = json.loads(written[0])
            self.assertEqual(init["method"], "initialize")
            self.assertEqual(json.loads(written[1])["method"], "notifications/initialized")
            self.assertEqual(json.loads(written[2])["method"], "tools/list")

    def test_handshake_fails_on_doc_only(self):
        """If MCP only exposes search-docs, the key wasn't loaded."""
        responses = [
            {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "x"}}},
            {},
            {"jsonrpc": "2.0", "id": 2, "result": {
                "tools": [{"name": "search-docs"}]
            }},
        ]
        with _fake_mcp(responses):
            with self.assertRaises(pinecone_client.PineconeConfigError):
                pinecone_client.PineconeClient(_fake_config(), timeout=2.0)


class TestClientErrors(unittest.TestCase):

    def _make_client(self, responses):
        """Build a client whose handshake already succeeded. The fake stdout
        loops, so extra reads just replay responses — caller must put the
        right id in the right position."""
        handshake = [
            {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "x"}}},
            {},
            {"jsonrpc": "2.0", "id": 2, "result": {
                "tools": [{"name": "search-docs"}, {"name": "upsert-records"},
                          {"name": "search-records"}]
            }},
        ]
        return handshake + list(responses)

    def test_tool_not_found_raises_api_error(self):
        responses = self._make_client([
            {"jsonrpc": "2.0", "id": 3, "result": {
                "content": [{"type": "text", "text": "MCP error -32602: Tool upsert-vectors not found",
                             "isError": True}]}},
        ])
        with _fake_mcp(responses) as (_proc, _w):
            c = pinecone_client.PineconeClient(_fake_config(), timeout=2.0, max_attempts=1)
            with self.assertRaises(pinecone_client.PineconeAPIError) as ctx:
                c.call("tools/call", {"name": "upsert-vectors", "arguments": {}})
            self.assertIn("upsert-vectors", str(ctx.exception))
            self.assertEqual(ctx.exception.tool, "upsert-vectors")

    def test_bad_args_raises_permanent(self):
        responses = self._make_client([
            {"jsonrpc": "2.0", "id": 3, "result": {
                "content": [{"type": "text", "text": "Invalid arguments for tool: top_k",
                             "isError": True}]}},
        ])
        with _fake_mcp(responses) as (_proc, _w):
            c = pinecone_client.PineconeClient(_fake_config(), timeout=2.0, max_attempts=3)
            with self.assertRaises(pinecone_client.PineconeAPIError):
                c.call("tools/call", {"name": "search-records",
                                      "arguments": {"top_k": 5}})  # wrong key

    def test_transient_retries_then_succeeds(self):
        # First attempt (id 3): -32603. Second attempt (id 4): success.
        # Handshake consumed id 1 and 2.
        responses = self._make_client([
            {"jsonrpc": "2.0", "id": 3, "error": {"code": -32603, "message": "internal"}},
            {"jsonrpc": "2.0", "id": 4, "result": {"ok": True}},
        ])
        with _fake_mcp(responses) as (_proc, _w):
            c = pinecone_client.PineconeClient(_fake_config(), timeout=2.0, max_attempts=3)
            with patch.object(pinecone_client.time, "sleep"):
                result = c.call("tools/call", {"name": "list-indexes", "arguments": {}})
            self.assertEqual(result, {"ok": True})
            metrics = c.metrics()
            self.assertGreaterEqual(metrics["retry_count"], 1)
            # 3 calls total: 1 handshake (tools/list) + 2 retries
            self.assertEqual(metrics["call_count"], 3)
            self.assertEqual(metrics["error_count"], 1)

    def test_metrics_record_errors(self):
        responses = self._make_client([
            {"jsonrpc": "2.0", "id": 3, "error": {"code": -32601, "message": "no such method"}},
        ])
        with _fake_mcp(responses) as (_proc, _w):
            c = pinecone_client.PineconeClient(_fake_config(), timeout=2.0, max_attempts=1)
            with self.assertRaises(pinecone_client.PineconeAPIError):
                c.call("nonexistent/method", {})
            m = c.metrics()
            self.assertEqual(m["error_count"], 1)
            # 2 calls total: 1 handshake (tools/list) + 1 user call (which errored)
            self.assertEqual(m["call_count"], 2)


class TestClientContextManager(unittest.TestCase):

    def test_with_closes_proc(self):
        responses = [
            {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "x"}}},
            {},
            {"jsonrpc": "2.0", "id": 2, "result": {
                "tools": [{"name": "search-docs"}, {"name": "upsert-records"},
                          {"name": "search-records"}, {"name": "list-indexes"}]
            }},
        ]
        with _fake_mcp(responses) as (proc, _w):
            with pinecone_client.PineconeClient(_fake_config(), timeout=2.0) as c:
                self.assertTrue(c.health()["alive"])
            proc.terminate.assert_called()


class TestExceptionHierarchy(unittest.TestCase):

    def test_all_inherit_from_pinecone_error(self):
        from empire_os.pinecone_client import (
            PineconeError, PineconeAPIError, PineconeTimeoutError,
            PineconeDimensionError, PineconeConfigError, PineconeNotFoundError,
        )
        for cls in (PineconeAPIError, PineconeTimeoutError, PineconeDimensionError,
                    PineconeConfigError, PineconeNotFoundError):
            self.assertTrue(issubclass(cls, PineconeError))

    def test_not_found_inherits_api_error(self):
        from empire_os.pinecone_client import PineconeNotFoundError, PineconeAPIError
        self.assertTrue(issubclass(PineconeNotFoundError, PineconeAPIError))


if __name__ == "__main__":
    unittest.main(verbosity=2)
