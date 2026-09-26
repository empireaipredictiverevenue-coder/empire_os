import io
import json
from unittest.mock import patch

from empire_os.coder.context import ContextPack
from empire_os.coder.llama_cpp_provider import LlamaCppProvider
from empire_os.coder.models import ModelRoute
from empire_os.coder.provider import ModelRequest


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_health_accepts_ready():
    with patch(
        "empire_os.coder.llama_cpp_provider.request.urlopen",
        return_value=FakeResponse(json.dumps({"status": "ok"}).encode()),
    ):
        assert LlamaCppProvider().health() is True


def test_provider_parses_openai_compatible_response():
    body = json.dumps({
        "choices": [{"message": {"content": "bounded patch plan"}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 5},
    }).encode()
    provider = LlamaCppProvider()
    req = ModelRequest(
        task_id="coder_test",
        instruction="Plan this change",
        context=ContextPack("goal", {}, (), (), 1000),
        route=ModelRoute(
            "llama_cpp", "qwen2.5-coder:7b", "local", True, 0
        ),
        max_output_chars=1000,
    )
    with patch(
        "empire_os.coder.llama_cpp_provider.request.urlopen",
        return_value=FakeResponse(body),
    ):
        result = provider.complete(req)
    assert result.error is None
    assert result.text == "bounded patch plan"
    assert result.usage["eval_count"] == 5


def test_provider_fails_closed_on_empty_choices():
    body = json.dumps({"choices": []}).encode()
    provider = LlamaCppProvider()
    req = ModelRequest(
        task_id="coder_test",
        instruction="Plan this change",
        context=ContextPack("goal", {}, (), (), 1000),
        route=ModelRoute(
            "llama_cpp", "qwen2.5-coder:7b", "local", True, 0
        ),
    )
    with patch(
        "empire_os.coder.llama_cpp_provider.request.urlopen",
        return_value=FakeResponse(body),
    ):
        result = provider.complete(req)
    assert result.error == "llama_cpp_empty_choices"
