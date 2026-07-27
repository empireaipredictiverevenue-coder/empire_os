#!/usr/bin/env python3
"""
pinecone_client.py — long-lived Pinecone MCP client.

One process per client. Initialize once at construction, send `notifications/
initialized` once, then issue `id`-incremented JSON-RPC requests over stdio.

Matches the pinecone-mcp-integration skill (see ~/.hermes/skills/).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from empire_os.pinecone_config import PinconeConfig, PineconeConfigError
from empire_os.pinecone_config import load as _load_config


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PineconeError(Exception):
    """Base. All other Pinecone errors inherit from this."""

    def __init__(self, msg: str, *, tool: str = "", call_args: Any = None,
                 mcp_error: str = "", attempt: int = 1, latency_ms: int = 0):
        super().__init__(msg)
        self.tool = tool
        self.call_args = call_args if call_args is not None else {}
        self.mcp_error = mcp_error
        self.attempt = attempt
        self.latency_ms = latency_ms


class PineconeAPIError(PineconeError):
    """MCP returned isError=true or an error field."""


class PineconeTimeoutError(PineconeError):
    """subprocess call exceeded the timeout."""


class PineconeDimensionError(PineconeError):
    """Embedding length does not match the configured expected dim."""


class PineconeConfigError(PineconeError):
    """Configuration is missing or invalid (raised at boot)."""


class PineconeNotFoundError(PineconeAPIError):
    """Index does not exist."""


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class _Metrics:
    call_count: int = 0
    error_count: int = 0
    retry_count: int = 0
    dim_mismatch_count: int = 0
    latencies_ms: deque[int] = field(default_factory=lambda: deque(maxlen=100))

    def record(self, latency_ms: int, error: bool) -> None:
        self.call_count += 1
        if error:
            self.error_count += 1
        self.latencies_ms.append(latency_ms)

    def snapshot(self) -> dict:
        n = len(self.latencies_ms)
        if n == 0:
            return {"call_count": self.call_count, "error_count": self.error_count,
                    "retry_count": self.retry_count, "dim_mismatch_count": self.dim_mismatch_count,
                    "p50_ms": 0, "p95_ms": 0, "error_rate": 0.0}
        sorted_lat = sorted(self.latencies_ms)
        p50 = sorted_lat[n // 2]
        p95 = sorted_lat[min(n - 1, int(n * 0.95))]
        return {
            "call_count": self.call_count,
            "error_count": self.error_count,
            "retry_count": self.retry_count,
            "dim_mismatch_count": self.dim_mismatch_count,
            "p50_ms": p50,
            "p95_ms": p95,
            "error_rate": self.error_count / self.call_count if self.call_count else 0.0,
        }


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(level: str, msg: str, **fields) -> None:
    """Structured JSON log to stdout. Never logs `text` payload or full API key."""
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": level,
        "msg": msg,
        "component": "pinecone_client",
    }
    rec.update(fields)
    # Defense in depth: scrub any field called 'api_key' or 'text' if it leaks.
    for k in ("api_key", "text"):
        if k in rec and isinstance(rec[k], str) and len(rec[k]) > 8:
            rec[k] = rec[k][:4] + "..." + rec[k][-2:]
    print(json.dumps(rec, default=str), flush=True)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

# Backoff: 200 ms, 500 ms, 1.5 s. Only applied to transient codes.
_BACKOFFS_MS = [200, 500, 1500]

# JSON-RPC error codes that warrant retry.
_TRANSIENT_RPC_CODES = {-32603}  # internal error

# JSON-RPC error codes that mean "your code is wrong, don't retry".
_PERMANENT_RPC_CODES = {-32600, -32601, -32602}


class PineconeClient:
    """Long-lived MCP client. One subprocess, persistent stdio pipes."""

    def __init__(self, config: PinconeConfig, *, timeout: float = 15.0,
                 max_attempts: int = 3, heartbeat_interval: float = 60.0,
                 start_new_session: bool = True):
        self._config = config
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._heartbeat_interval = heartbeat_interval
        self._metrics = _Metrics()
        self._proc: Optional[subprocess.Popen] = None
        self._id_counter = 0
        self._last_io_at = 0.0
        self._start_new_session = start_new_session
        self._start()
        self._handshake()

    # -- lifecycle ----------------------------------------------------------

    def _start(self) -> None:
        env = {**os.environ, "PINECONE_API_KEY": self._config.api_key}
        try:
            self._proc = subprocess.Popen(
                ["npx", "-y", "@pinecone-database/mcp"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1,  # line-buffered
                start_new_session=self._start_new_session,
            )
        except FileNotFoundError as e:
            raise PineconeConfigError(
                "npx not on PATH — install Node.js (npx ships with it)"
            ) from e

    def _handshake(self) -> None:
        """Send initialize + notifications/initialized. Verify tools come back."""
        self._send_raw({
            "jsonrpc": "2.0", "id": self._next_id(), "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "empire-pinecone", "version": "2.0"},
            },
        })
        self._send_raw({"jsonrpc": "2.0", "method": "notifications/initialized"})
        # Probe tools so we fail fast if the key is invalid.
        tools = self.call("tools/list", {})
        names = sorted(t.get("name", "?") for t in tools.get("tools", []))
        if "search-docs" in names and len(names) < 3:
            raise PineconeConfigError(
                "MCP server only exposes doc search — PINECONE_API_KEY invalid or not loaded"
            )
        _log("INFO", "mcp_handshake_ok", tools=names, index=self._config.index,
             dim=self._config.dimension, embed=self._config.embed_model,
             key=self._config.redact_key())

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=2)
        self._proc = None

    def __enter__(self) -> "PineconeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    # -- core call ----------------------------------------------------------

    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    def _send_raw(self, msg: dict) -> None:
        assert self._proc and self._proc.stdin
        line = json.dumps(msg) + "\n"
        try:
            self._proc.stdin.write(line)
            self._proc.stdin.flush()
        except (BrokenPipeError, ValueError) as e:
            raise PineconeAPIError(
                f"MCP subprocess stdin closed: {e}", tool=msg.get("method", "?")
            ) from e
        self._last_io_at = time.monotonic()

    def _read_response(self, expected_id: int, timeout: float) -> dict:
        """Read lines until we see the response matching expected_id, or timeout."""
        assert self._proc and self._proc.stdout
        deadline = time.monotonic() + timeout
        leftover = ""
        while True:
            if time.monotonic() > deadline:
                raise PineconeTimeoutError(
                    "MCP response timeout", attempt=1,
                    latency_ms=int((time.monotonic() - (deadline - timeout)) * 1000)
                )
            line = self._proc.stdout.readline()
            if not line:
                # EOF — could mean subprocess died or stdout closed
                rc = self._proc.poll()
                raise PineconeAPIError(
                    f"MCP subprocess stdout closed (rc={rc}) before responding"
                )
            self._last_io_at = time.monotonic()
            line = leftover + line
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                leftover = line
                continue
            if obj.get("id") == expected_id:
                return obj
            # Not our response — keep reading (shouldn't happen with id, but be safe)

    def call(self, method: str, params: dict) -> dict:
        """
        Issue one JSON-RPC request with retry-on-transient.

        Returns the parsed `result` object. Raises PineconeError subclasses
        on any failure. No silent error returns.
        """
        tool = ""
        if method == "tools/call" and isinstance(params, dict):
            tool = params.get("name", "")

        last_err: Optional[PineconeError] = None
        for attempt in range(1, self._max_attempts + 1):
            t0 = time.monotonic()
            rid = self._next_id()
            try:
                self._send_raw({"jsonrpc": "2.0", "id": rid, "method": method,
                                "params": params})
                resp = self._read_response(rid, self._timeout)
            except PineconeTimeoutError as e:
                e.attempt = attempt
                e.tool = tool
                e.latency_ms = int((time.monotonic() - t0) * 1000)
                last_err = e
                self._metrics.retry_count += 1
                _log("WARN", "mcp_timeout_retry", attempt=attempt, tool=tool)
                self._backoff(attempt)
                continue
            except PineconeAPIError as e:
                # subprocess died — restart once
                if attempt < self._max_attempts:
                    _log("WARN", "mcp_subprocess_died_restarting", attempt=attempt, tool=tool)
                    self._restart_subprocess()
                    self._metrics.retry_count += 1
                    self._backoff(attempt)
                    continue
                raise

            latency_ms = int((time.monotonic() - t0) * 1000)

            if "error" in resp:
                code = resp["error"].get("code", 0)
                msg = resp["error"].get("message", "unknown")
                err = PineconeAPIError(f"JSON-RPC error: {msg}", tool=tool,
                                       mcp_error=msg, attempt=attempt, latency_ms=latency_ms)
                self._metrics.record(latency_ms, error=True)
                if code in _PERMANENT_RPC_CODES:
                    raise err
                if code in _TRANSIENT_RPC_CODES and attempt < self._max_attempts:
                    _log("WARN", "mcp_transient_retry", attempt=attempt, code=code, tool=tool)
                    self._metrics.retry_count += 1
                    self._backoff(attempt)
                    continue
                raise err

            result = resp.get("result", {})
            # The MCP server embeds isError inside result.content[0] for tool calls.
            # For other methods, isError doesn't apply — result is the result.
            if method == "tools/call" and isinstance(result, dict):
                content = result.get("content") or []
                if content and isinstance(content, list):
                    first = content[0] or {}
                    if first.get("isError"):
                        err_text = (first.get("text") or "")[:300]
                        # -32602 → bad args, don't retry
                        if "Tool" in err_text and "not found" in err_text:
                            self._metrics.record(latency_ms, error=True)
                            raise PineconeAPIError(
                                f"tool not found: {tool}", tool=tool,
                                mcp_error=err_text, attempt=attempt, latency_ms=latency_ms)
                        if "Invalid arguments" in err_text:
                            self._metrics.record(latency_ms, error=True)
                            raise PineconeAPIError(
                                f"bad args for {tool}", tool=tool,
                                mcp_error=err_text, attempt=attempt, latency_ms=latency_ms)
                        if "not found" in err_text.lower() and "index" in err_text.lower():
                            self._metrics.record(latency_ms, error=True)
                            raise PineconeNotFoundError(
                                f"index not found", tool=tool,
                                mcp_error=err_text, attempt=attempt, latency_ms=latency_ms)
                        # Otherwise treat as transient and retry
                        if attempt < self._max_attempts:
                            _log("WARN", "mcp_tool_error_retry",
                                 attempt=attempt, tool=tool, mcp=err_text[:200])
                            self._metrics.retry_count += 1
                            self._backoff(attempt)
                            continue
                        self._metrics.record(latency_ms, error=True)
                        raise PineconeAPIError(
                            f"tool {tool} failed: {err_text[:200]}",
                            tool=tool, mcp_error=err_text,
                            attempt=attempt, latency_ms=latency_ms)
            self._metrics.record(latency_ms, error=False)
            return result

        # Exhausted retries
        if last_err:
            raise last_err
        raise PineconeAPIError("exhausted retries with no recorded error",
                               tool=tool, attempt=self._max_attempts)

    def _backoff(self, attempt: int) -> None:
        idx = min(attempt - 1, len(_BACKOFFS_MS) - 1)
        delay_ms = _BACKOFFS_MS[idx]
        # 50% jitter
        jitter = delay_ms * 0.5 * (uuid.uuid4().int % 100) / 100
        time.sleep((delay_ms + jitter) / 1000.0)

    def _restart_subprocess(self) -> None:
        self.close()
        self._start()
        self._handshake()

    # -- convenience --------------------------------------------------------

    def health(self) -> dict:
        """Return metrics + process liveness. Cheap; safe to call often."""
        alive = self._proc is not None and self._proc.poll() is None
        return {"alive": alive, **self._metrics.snapshot()}

    @property
    def config(self) -> PinconeConfig:
        return self._config

    def metrics(self) -> dict:
        return self._metrics.snapshot()


def get_client() -> PineconeClient:
    """Factory: load config + build client. Use as `with get_client() as c:`."""
    return PineconeClient(_load_config())


if __name__ == "__main__":
    # Manual smoke: `python3 pinecone_client.py`
    with get_client() as c:
        print(json.dumps(c.health(), indent=2), file=sys.stderr)
        indexes = c.call("tools/call", {"name": "list-indexes", "arguments": {}})
        print(json.dumps(indexes, indent=2))
