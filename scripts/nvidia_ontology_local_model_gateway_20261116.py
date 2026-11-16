"""Local-only NVIDIA ontology evaluation model gateway.

A strict, non-billing HTTP proxy to the existing host Ollama service. It binds
only to the isolated Docker sandbox bridge gateway, and accepts traffic only
from that bridge. Requests do not leave EmpireOS.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HOST = os.getenv("EMPIRE_NVIDIA_EVAL_MODEL_HOST", "172.18.0.1")
PORT = int(os.getenv("EMPIRE_NVIDIA_EVAL_MODEL_PORT", "19999"))
SOURCE_NET = ipaddress.ip_network("172.18.0.0/16")
UPSTREAM = "http://127.0.0.1:11434"
MAX_BYTES = 1_048_576
MAX_RESPONSE_BYTES = 8_388_608
INFERENCE_SLOTS = threading.BoundedSemaphore(4)
ALLOWED_MODELS = {
    "/v1/chat/completions": frozenset({"openai/qwen2.5-coder:1.5b"}),
    "/v1/embeddings": frozenset({"nomic-embed-text", "nomic-embed-text:latest"}),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "EmpireOntologyLocalModelGateway/1.0"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        # No prompts, source data, authorization headers or request bodies.
        return

    def _reply(self, code: int, payload: bytes, *, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _allowed_client(self) -> bool:
        try:
            addr = ipaddress.ip_address(self.client_address[0])
        except ValueError:
            return False
        return (addr in SOURCE_NET or addr.is_loopback)

    def do_GET(self) -> None:
        if not self._allowed_client():
            self._reply(403, b'{"error":"forbidden source"}')
            return
        if self.path == "/health":
            try:
                with urlopen(UPSTREAM + "/api/version", timeout=4) as response:
                    upstream_ok = response.status == 200
            except (HTTPError, URLError, TimeoutError, OSError):
                upstream_ok = False
            code = 200 if upstream_ok else 503
            self._reply(code, json.dumps({
                "status": "ok" if upstream_ok else "ollama_unavailable",
                "local_only": True,
                "configured_models": 2,
            }).encode())
            return
        if self.path != "/v1/models":
            self._reply(404, b'{"error":"unsupported path"}')
            return
        self._forward("GET", None)

    def do_POST(self) -> None:
        if not self._allowed_client():
            self._reply(403, b'{"error":"forbidden source"}')
            return
        if self.path not in ALLOWED_MODELS:
            self._reply(404, b'{"error":"unsupported path"}')
            return
        size = self.headers.get("Content-Length")
        if size is None or not size.isdigit() or not (1 <= int(size) <= MAX_BYTES):
            self._reply(413, b'{"error":"invalid request length"}')
            return
        data = self.rfile.read(int(size))
        try:
            payload = json.loads(data)
            if not isinstance(payload, dict) or payload.get("model") not in ALLOWED_MODELS[self.path]:
                raise ValueError("model not allowlisted")
            # Only JSON, no streaming, no arbitrary URL or tool invocation.
            if self.path == "/v1/chat/completions" and payload.get("stream", False):
                self._reply(422, b'{"error":"streaming not enabled on private gateway"}')
                return
        except (ValueError, UnicodeError, json.JSONDecodeError):
            self._reply(422, b'{"error":"model or request invalid"}')
            return
        self._forward("POST", data)

    def _forward(self, method: str, data: bytes | None) -> None:
        if not INFERENCE_SLOTS.acquire(blocking=False):
            self._reply(429, b'{"error":"local model busy"}')
            return
        try:
            request = Request(
                UPSTREAM + self.path, data=data, method=method,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            try:
                with urlopen(request, timeout=180) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                    if len(body) > MAX_RESPONSE_BYTES:
                        self._reply(502, b'{"error":"model response too large"}')
                    else:
                        self._reply(response.status, body)
            except HTTPError as exc:
                body = exc.read(4096)
                self._reply(
                    exc.code, body if body else b'{"error":"local model request rejected"}'
                )
            except (URLError, TimeoutError, OSError):
                self._reply(503, b'{"error":"local model unavailable"}')
        finally:
            INFERENCE_SLOTS.release()


def serve() -> None:
    if HOST not in {"172.18.0.1", "127.0.0.1"}:
        raise RuntimeError("refusing non-reviewable bind address")
    with socket.socket() as probe:
        probe.bind((HOST, 0))
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.daemon_threads = True
    httpd.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    serve()
