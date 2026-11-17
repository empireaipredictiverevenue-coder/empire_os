"""Contract tests: the NVIDIA evaluation model gateway must remain local-only."""
from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from scripts.nvidia_ontology_local_model_gateway_20261116 import (
    ALLOWED_MODELS, Handler, HOST, PORT, SOURCE_NET, UPSTREAM,
)


def _call(base: str, path: str, payload: dict | None = None):
    body = None if payload is None else json.dumps(payload).encode()
    request = Request(
        base + path, data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=45) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def test_bound_endpoint_is_private_and_not_external():
    assert HOST == "172.18.0.1"
    assert PORT == 19999
    assert str(SOURCE_NET) == "172.18.0.0/16"
    assert UPSTREAM == "http://127.0.0.1:11434"
    assert set(ALLOWED_MODELS) == {"/v1/chat/completions", "/v1/embeddings"}
    assert ALLOWED_MODELS["/v1/chat/completions"] == {
        "openai/qwen2.5-coder:1.5b",
        "openai/nvidia/nemotron-3.5-super-vl:free",
    }


def test_local_ollama_and_denied_requests():
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            assert _call(base, "/health")[0] == 200
            assert _call(base, "/api/tags")[0] == 404
            assert _call(base, "/v1/chat/completions", {
                "model": "unauthorised-model",
                "messages": [{"role": "user", "content": "hi"}],
            })[0] == 422
            assert _call(base, "/v1/chat/completions", {
                "model": "openai/qwen2.5-coder:1.5b", "stream": True,
                "messages": [{"role": "user", "content": "hi"}],
            })[0] == 422
            code, result = _call(base, "/v1/embeddings", {
                "model": "nomic-embed-text",
                "input": ["synthetic buyer permit relationship"],
                "input_type": "passage", "truncate": "END", "modality": "text",
            })
            assert code == 200
            assert len(result["data"]) == 1
            assert len(result["data"][0]["embedding"]) == 768
        finally:
            server.shutdown()
            thread.join(timeout=5)
