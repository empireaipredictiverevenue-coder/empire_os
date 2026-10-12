"""Live call surface never presents a dial URI without the gated reservation."""
from __future__ import annotations

from fastapi.testclient import TestClient

from empire_os import public_gateway
from empire_os import lead_smart_pilot_call_api as handoff

CLIENT = TestClient(public_gateway.app)


def test_handoff_denied_by_default_and_no_phone_disclosed():
    response = CLIENT.post(
        "/roofing/pilot-handoff", data={"zip": "10001"},
        headers={"origin": "https://empire-ai.co.uk"},
    )
    assert response.status_code == 503
    assert "tel:" not in response.text
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_external_origin_and_invalid_requests_denied_without_call(monkeypatch):
    monkeypatch.setattr(handoff, "call_available", lambda _: True)
    monkeypatch.setattr(handoff, "reserve_site_handoff",
                        lambda *_args, **_kw: (_ for _ in ()).throw(
                            AssertionError("must never reserve")))
    wrong = CLIENT.post("/roofing/pilot-handoff", data={"zip": "10001"},
                        headers={"origin": "https://example.org"})
    assert wrong.status_code == 403
    oversized = CLIENT.post("/roofing/pilot-handoff", data={"zip": "1"*120}, headers={"origin": "https://empire-ai.co.uk"})
    assert oversized.status_code == 422
    extra = CLIENT.post("/roofing/pilot-handoff", data={"zip": "10001", "id": "x"}, headers={"origin": "https://empire-ai.co.uk"})
    assert extra.status_code == 422


def test_handoff_returns_explicit_final_phone_choice_only_after_admission(monkeypatch):
    monkeypatch.setattr(handoff, "call_available", lambda zip_code: zip_code == "10001")
    monkeypatch.setattr(handoff, "_json", lambda _path: {"status": "test"})
    monkeypatch.setattr(handoff, "_in_current_coverage", lambda _zip: True)
    calls = []
    def reserve(zip_code, **_kw):
        calls.append(zip_code)
        return "tel:+18883579305"
    monkeypatch.setattr(handoff, "reserve_site_handoff", reserve)
    response = CLIENT.post(
        "/roofing/pilot-handoff", data={"zip": "10001"},
        headers={"origin": "https://empire-ai.co.uk"},
    )
    assert response.status_code == 200
    assert "href='tel:+18883579305'" in response.text
    assert "http-equiv='refresh'" not in response.text
    assert calls == ["10001"]
    assert "10001" not in response.text
    assert response.headers["cache-control"].startswith("no-store")


def test_denied_zip_and_failed_reservation_never_reveal_phone(monkeypatch):
    monkeypatch.setattr(handoff, "call_available", lambda _: False)
    denied = CLIENT.post("/roofing/pilot-handoff", data={"zip": "10001"}, headers={"origin": "https://empire-ai.co.uk"})
    assert denied.status_code == 503
    assert "tel:" not in denied.text
    monkeypatch.setattr(handoff, "call_available", lambda _: True)
    from empire_os.lead_smart_site_handoff import HandoffHeld
    def unavailable(*_args, **_kwargs):
        raise HandoffHeld()
    monkeypatch.setattr(handoff, "reserve_site_handoff", unavailable)
    denied_again = CLIENT.post("/roofing/pilot-handoff", data={"zip": "10001"}, headers={"origin": "https://empire-ai.co.uk"})
    assert denied_again.status_code == 503
    assert "tel:" not in denied_again.text
