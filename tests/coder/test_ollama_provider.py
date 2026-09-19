import io
import json
from unittest.mock import patch

from empire_os.coder.context import ContextPack
from empire_os.coder.models import ModelRoute
from empire_os.coder.ollama_provider import OllamaProvider
from empire_os.coder.provider import ModelRequest


class FakeResponse(io.BytesIO):
    status = 200
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()


def test_ollama_provider_returns_local_response():
    body = json.dumps({
        "message": {"content": "patch plan"},
        "prompt_eval_count": 10,
        "eval_count": 5,
    }).encode()
    provider = OllamaProvider()
    req = ModelRequest(
        task_id="coder_test",
        instruction="Inspect this module",
        context=ContextPack("goal", {}, (), (), 1000),
        route=ModelRoute(
            "ollama", "qwen3-coder:30b", "local", True, 0
        ),
    )
    with patch(
        "empire_os.coder.ollama_provider.request.urlopen",
        return_value=FakeResponse(body),
    ):
        result = provider.complete(req)
    assert result.provider == "ollama"
    assert result.model == "qwen3-coder:30b"
    assert result.text == "patch plan"
    assert result.usage["eval_count"] == 5


def test_ollama_provider_caps_prompt_and_prediction():
    captured = {}
    body = json.dumps({
        "message": {"content": "ok"},
        "prompt_eval_count": 1,
        "eval_count": 1,
    }).encode()

    def fake_urlopen(req, timeout):
        captured["payload"] = json.loads(req.data.decode())
        return FakeResponse(body)

    provider = OllamaProvider(context_length=16384, num_threads=8)
    req = ModelRequest(
        task_id="coder_test",
        instruction="x" * 200_000,
        context=ContextPack("goal", {}, (), (), 1000),
        route=ModelRoute("ollama", "qwen3-coder:30b", "local", True, 0),
        max_output_chars=100_000,
    )
    with patch(
        "empire_os.coder.ollama_provider.request.urlopen",
        side_effect=fake_urlopen,
    ):
        provider.complete(req)
    payload = captured["payload"]
    assert len(payload["messages"][1]["content"]) <= 49152
    assert payload["options"]["num_predict"] == 2048
    assert payload["options"]["num_ctx"] == 16384
    assert payload["options"]["num_thread"] == 8
    assert payload["think"] is False
    assert "BLUEPRINT_V6.md" in payload["messages"][0]["content"]
