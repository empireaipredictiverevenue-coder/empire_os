from fastapi.testclient import TestClient

from empire_os.hub import app


client = TestClient(app)


def test_email_compose_is_draft_only_and_current_payment_rail():
    response = client.post(
        "/v1/email/compose",
        json={
            "email": "buyer@example.com",
            "name": "Alex",
            "niche": "roofing",
            "metro": "London",
            "state": "GB",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "DRAFT"
    assert body["sent"] is False
    assert body["execution_authority"] == "none"
    assert "USDT on BSC" in body["body"]
    assert "USDC on Solana" not in body["body"]
    assert "free 1-day trial" not in body["body"]


def test_copy_draft_is_non_sending_and_current_payment_rail():
    response = client.post(
        "/v1/copy",
        json={
            "name": "Alex",
            "niche": "roofing",
            "metro": "London",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "DRAFT"
    assert body["sent"] is False
    assert body["execution_authority"] == "none"
    assert "USDT on BSC" in body["body"]
    assert "USDC on Solana" not in body["body"]
    assert "best fit" not in body["body"]


def test_seo_audit_file_writer_is_retired():
    response = client.post(
        "/v1/seo/audit",
        json={"results": [{"url": "https://example.com"}]},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_seo_audit_retired_use_search_intelligence_evidence_flow"
    )


def test_mass_torts_direct_is_observation_only():
    response = client.post(
        "/v1/mass-torts/direct",
        json={"niche": "mass-tort", "signals": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["persisted"] is False
    assert body["execution_authority"] == "none"


def test_media_schedule_is_still_non_executing():
    response = client.post(
        "/v1/media/schedule",
        json={"channel": "linkedin"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scheduled"] is False
    assert body["execution_authority"] == "none"
