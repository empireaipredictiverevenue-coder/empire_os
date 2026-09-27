import io
import json
from urllib.error import HTTPError

import pytest

import empire_os.data_backends.astra_token_legacy as legacy
from empire_os.data_backends.astra_token_legacy import (
    LegacyAstraTokenBackend,
    legacy_astra_backend_from_environment,
)
from empire_os.outcome_role_transport import OutcomeTransportError


@pytest.fixture(autouse=True)
def isolate_egress_guard(monkeypatch):
    monkeypatch.setattr(legacy, "_reserve_supabase_request", lambda: None)
    monkeypatch.setattr(legacy, "_close_supabase_egress_circuit", lambda: None)
    monkeypatch.setattr(
        legacy,
        "_open_supabase_egress_circuit",
        lambda _reason: None,
    )


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def __call__(self, request, timeout=15):
        self.requests.append((request, timeout))
        return FakeResponse(self.payload)


def make_backend(tmp_path, payload):
    token_file = tmp_path / "observer_token"
    token_file.write_text("a" * 64, encoding="utf-8")
    opener = FakeOpener(payload)
    backend = LegacyAstraTokenBackend(
        "https://example.supabase.co",
        "sb_publishable_test",
        token_file,
        opener=opener,
    )
    return backend, opener


def test_feedback_rpc_uses_token_wrapper_only(tmp_path):
    backend, opener = make_backend(
        tmp_path,
        [{"actual_revenue_cents": 10000}],
    )

    result = backend.call(
        "get_commercial_outcome_feedback",
        {"p_limit": 25},
    )

    assert result[0]["actual_revenue_cents"] == 10000
    request, timeout = opener.requests[0]
    assert timeout == 15
    assert request.full_url.endswith(
        "/rest/v1/rpc/get_commercial_outcome_feedback_token"
    )
    body = json.loads(request.data.decode("utf-8"))
    assert body["p_token"] == "a" * 64
    assert body["p_limit"] == 25


def test_quota_402_opens_shared_egress_circuit(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(
        legacy,
        "_open_supabase_egress_circuit",
        lambda reason: opened.append(reason),
    )

    def opener(request, timeout=15):
        raise HTTPError(
            request.full_url,
            402,
            "Payment Required",
            hdrs=None,
            fp=io.BytesIO(
                b'{"message":"restricted due to the following violations: exceed_egress_quota"}'
            ),
        )

    token_file = tmp_path / "observer_token"
    token_file.write_text("a" * 64, encoding="utf-8")
    backend = LegacyAstraTokenBackend(
        "https://example.supabase.co",
        "sb_publishable_test",
        token_file,
        opener=opener,
    )

    with pytest.raises(OutcomeTransportError):
        backend.call("get_astra_operational_evidence", {})

    assert opened == ["exceed_egress_quota"]


def test_https_and_token_file_are_required(tmp_path):
    token_file = tmp_path / "observer_token"
    token_file.write_text("a" * 64, encoding="utf-8")

    with pytest.raises(OutcomeTransportError, match="HTTPS"):
        LegacyAstraTokenBackend(
            "http://example.supabase.co",
            "key",
            token_file,
        )
    with pytest.raises(OutcomeTransportError, match="token file"):
        LegacyAstraTokenBackend(
            "https://example.supabase.co",
            "key",
            tmp_path / "missing",
        )


def test_generic_env_names_take_precedence(tmp_path):
    token_file = tmp_path / "observer_token"
    token_file.write_text("a" * 64, encoding="utf-8")

    backend = legacy_astra_backend_from_environment({
        "EMPIRE_ASTRA_LEGACY_URL": "https://generic.example",
        "EMPIRE_ASTRA_LEGACY_PUBLISHABLE_KEY": "generic-key",
        "EMPIRE_ASTRA_SUPABASE_URL": "https://old.example",
        "EMPIRE_ASTRA_SUPABASE_PUBLISHABLE_KEY": "old-key",
        "EMPIRE_ASTRA_OBSERVER_TOKEN_FILE": str(token_file),
    })

    assert backend is not None
    assert backend.base_url == "https://generic.example"
    assert backend.publishable_key == "generic-key"
