import json
from io import BytesIO
from urllib.error import HTTPError

import empire_os.aider_model_selector as selector


class _Response:
    def __init__(self, payload, status=200):
        self.status = status
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_selector_falls_back_after_429(monkeypatch):
    monkeypatch.setattr(
        selector,
        "_protected_omniroute_env",
        lambda: {
            "OPENAI_BASE_URL": "http://127.0.0.1:20128/v1",
            "OPENAI_API_KEY": "secret",
            "EMPIRE_HERMES_MODEL": "provider/preferred-coder",
        },
    )

    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url)
        if req.full_url.endswith("/models"):
            return _Response({
                "data": [
                    {"id": "provider/backup-coder"},
                    {"id": "provider/general"},
                ]
            })
        body = json.loads(req.data.decode("utf-8"))
        model = body["model"]
        if model == "provider/preferred-coder":
            raise HTTPError(
                req.full_url,
                429,
                "Too Many Requests",
                hdrs=None,
                fp=BytesIO(b"{}"),
            )
        if model == "auto":
            return _Response({
                "choices": [{"message": {"content": ""}}]
            })
        if model == "provider/backup-coder":
            return _Response({
                "choices": [{
                    "message": {"content": "EMPIRE_CODER_OK"}
                }]
            })
        raise AssertionError(model)

    monkeypatch.setattr(selector.urlrequest, "urlopen", fake_urlopen)

    result = selector.select_usable_aider_model(
        timeout_seconds=1,
        max_candidates=6,
    )

    assert result["selected_direct_model"] == "provider/backup-coder"
    assert result["selected"] == "openai/provider/backup-coder"
    assert result["reason"] == "usable_model_selected"
    assert result["attempts"][0]["http_status"] == 429
    assert result["attempts"][-1]["usable"] is True
    assert result["execution_authority"] == "none"


def test_selector_fails_closed_when_no_model_usable(monkeypatch):
    monkeypatch.setattr(
        selector,
        "_protected_omniroute_env",
        lambda: {
            "OPENAI_BASE_URL": "http://127.0.0.1:20128/v1",
            "OPENAI_API_KEY": "secret",
            "EMPIRE_HERMES_MODEL": "provider/preferred",
        },
    )

    def fake_urlopen(req, timeout=0):
        if req.full_url.endswith("/models"):
            return _Response({"data": []})
        return _Response({
            "choices": [{"message": {"content": ""}}]
        })

    monkeypatch.setattr(selector.urlrequest, "urlopen", fake_urlopen)

    result = selector.select_usable_aider_model(
        timeout_seconds=1,
        max_candidates=3,
    )

    assert result["selected"] is None
    assert result["reason"] == "no_usable_model"
    assert result["execution_authority"] == "none"
