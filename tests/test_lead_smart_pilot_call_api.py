"""Live call surface never presents a dial URI without the gated reservation."""
from __future__ import annotations

from fastapi.testclient import TestClient

from empire_os import public_gateway
from empire_os import lead_smart_pilot_call_api as handoff

CLIENT = TestClient(public_gateway.app)


def test_handoff_denied_by_default_and_no_phone_disclosed(monkeypatch):
    monkeypatch.setattr(handoff, "call_available", lambda _zip: False)
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
    for bad in ("no", "true", "1", "YES", ""):
        denied = CLIENT.post("/roofing/pilot-handoff",
                             data={"zip": "10001", "recording_consent": bad},
                             headers={"origin": "https://empire-ai.co.uk"})
        assert denied.status_code == 422
        assert "tel:" not in denied.text


def test_handoff_returns_explicit_final_phone_choice_only_after_admission(monkeypatch):
    monkeypatch.setattr(handoff, "call_available", lambda zip_code: zip_code == "10001")
    monkeypatch.setattr(handoff, "_json", lambda _path: {"status": "test"})
    monkeypatch.setattr(handoff, "_in_current_coverage", lambda _zip: True)
    calls = []
    def reserve(zip_code, **_kw):
        calls.append(zip_code)
        return "tel:+18883579305"
    monkeypatch.setattr(handoff, "reserve_site_handoff", reserve)
    preview = CLIENT.post(
        "/roofing/pilot-handoff", data={"zip": "10001"},
        headers={"origin": "https://empire-ai.co.uk"},
    )
    assert preview.status_code == 200
    assert "href='tel:" not in preview.text
    assert "recording_consent" in preview.text
    assert "keeps call recordings indefinitely" in preview.text
    assert calls == []  # Merely previewing must not consume a permit.
    response = CLIENT.post(
        "/roofing/pilot-handoff", data={"zip": "10001", "recording_consent": "yes"},
        headers={"origin": "https://empire-ai.co.uk"},
    )
    assert response.status_code == 200
    assert "href='tel:+18883579305'" in response.text
    assert "<strong>Recording notice:</strong>" in response.text
    assert "Additional in-call notice" not in response.text
    assert "additional in-call notice and consent requirements" in response.text
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
    denied_again = CLIENT.post("/roofing/pilot-handoff", data={"zip": "10001", "recording_consent": "yes"}, headers={"origin": "https://empire-ai.co.uk"})
    assert denied_again.status_code == 503
    assert "tel:" not in denied_again.text


def test_acknowledgment_rechecks_live_eligibility_before_phone(monkeypatch):
    count = [0]
    def changing(_zip):
        count[0] += 1
        return count[0] == 1
    monkeypatch.setattr(handoff, "call_available", changing)
    monkeypatch.setattr(handoff, "reserve_site_handoff",
                        lambda *_a, **_k: (_ for _ in ()).throw(
                            AssertionError("must not reserve after stop")))
    first = CLIENT.post("/roofing/pilot-handoff", data={"zip": "60601"},
                        headers={"origin": "https://empire-ai.co.uk"})
    assert first.status_code == 200
    assert "href='tel:" not in first.text
    second = CLIENT.post("/roofing/pilot-handoff",
                         data={"zip": "60601", "recording_consent": "yes"},
                         headers={"origin": "https://empire-ai.co.uk"})
    assert second.status_code == 503
    assert "tel:" not in second.text


def test_acknowledgment_must_be_singular_not_duplicate(monkeypatch):
    monkeypatch.setattr(handoff, "call_available", lambda _zip: True)
    monkeypatch.setattr(handoff, "reserve_site_handoff",
                        lambda *_a, **_k: (_ for _ in ()).throw(
                            AssertionError("duplicate consent must not reserve")))
    d = CLIENT.post("/roofing/pilot-handoff",
                    content="zip=60601&recording_consent=yes&recording_consent=yes",
                    headers={"origin": "https://empire-ai.co.uk",
                             "content-type": "application/x-www-form-urlencoded"})
    assert d.status_code == 422
    assert "tel:" not in d.text


def test_released_policy_presence_uses_canonical_empire_public_legal_receipts(monkeypatch):
    # The public policies are served from empire_ai_public_legal_release.
    # The reviewed-content receipt is an unrelated homeowner guide release.
    import empire_os.empire_ai_public_legal_release as legal
    seen=[]
    monkeypatch.setattr(legal, "checked_legal_path", lambda route: (
        seen.append(route) or ("/approved/"+route+".html")
    ))
    assert handoff._released_privacy_terms() is True
    assert seen == ["privacy", "terms"]


def test_missing_real_terms_release_still_blocks(monkeypatch):
    import empire_os.empire_ai_public_legal_release as legal
    monkeypatch.setattr(legal, "checked_legal_path", lambda route: (
        "/approved/privacy.html" if route == "privacy" else None
    ))
    assert handoff._released_privacy_terms() is False


def test_roofing_call_privacy_is_public_without_launch_and_says_who_handles_recording():
    response = CLIENT.get("/roofing/call-privacy")
    assert response.status_code == 200
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert response.headers["cache-control"].startswith("no-store")
    assert "tel:" not in response.text
    assert "Lead Smart" in response.text
    assert "Ringba" in response.text
    assert "may begin when a call is answered or earlier" in response.text
    assert "retained indefinitely" in response.text
    assert "founder@empire-ai.co.uk" in response.text
    assert "does not independently control" in response.text


def test_roofing_consent_page_links_specific_notice_not_only_youtube_policy(monkeypatch):
    monkeypatch.setattr(handoff, "call_available", lambda _zip: True)
    monkeypatch.setattr(handoff, "reserve_site_handoff", lambda *_args,**_kwargs: (
        (_ for _ in ()).throw(AssertionError("pre-consent cannot reserve"))
    ))
    response = CLIENT.post(
        "/roofing/pilot-handoff", data={"zip":"60601"},
        headers={"origin":"https://empire-ai.co.uk"},
    )
    assert response.status_code == 200
    assert "/roofing/call-privacy" in response.text
    assert "recording_consent" in response.text
    assert "tel:" not in response.text
