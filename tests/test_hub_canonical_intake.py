from fastapi.testclient import TestClient

from empire_os.hub import app


client = TestClient(app)


def test_hub_intake_converges_on_canonical_prospect(monkeypatch):
    observed = {}

    def fake_ingest(candidate):
        observed.update(candidate)
        return {
            "decision": "created",
            "prospect": {"id": "prospect-123"},
        }

    monkeypatch.setattr(
        "empire_os.crawler_runner.ingest_candidate",
        fake_ingest,
    )

    response = client.post(
        "/v1/hub/intake",
        json={
            "name": "Acme Roofing Ltd",
            "niche": "roofing",
            "metro": "London",
            "email": "owner@example.com",
            "phone": "+442000000000",
            "text": "Commercial roofing contractor",
            "source": "partner_feed",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["prospect_id"] == "prospect-123"
    assert body["status"] == "canonical_owned"
    assert body["canonical_store"] == "supabase"
    assert body["legacy_lane_write"] is False
    assert observed["name"] == "Acme Roofing Ltd"
    assert observed["source"] == "partner_feed"
    assert observed["raw"]["metadata"]["compat_route"] == "/v1/hub/intake"
    assert observed["raw"]["metadata"]["payload_hash"] == body["labels"]["payload_hash"]


def test_hub_intake_requires_business_identity_fields():
    response = client.post(
        "/v1/hub/intake",
        json={"text": "something happened"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "name, niche and metro required"


def test_hub_intake_conflict_fails_for_manual_resolution(monkeypatch):
    def ambiguous(candidate):
        return {
            "decision": "ambiguous",
            "reason": "multiple candidate identities",
        }

    monkeypatch.setattr(
        "empire_os.crawler_runner.ingest_candidate",
        ambiguous,
    )

    response = client.post(
        "/v1/hub/intake",
        json={
            "name": "Acme Roofing Ltd",
            "niche": "roofing",
            "metro": "London",
        },
    )
    assert response.status_code == 409
    assert "manual resolution" in response.json()["detail"]


def test_satellite_strike_no_longer_creates_fake_crm_lead():
    response = client.post(
        "/v1/satellite/strike",
        json={"event": "Severe Thunderstorm", "area": "London"},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_satellite_strike_crm_mutation_retired_use_signal_and_canonical_acquisition_flow"
    )


def test_legacy_outreach_mutations_are_retired():
    register = client.post(
        "/v1/outreach/prospect/register",
        json={"prospect_id": "prospect-1"},
    )
    touched = client.post(
        "/v1/outreach/prospect/touched",
        json={"prospect_id": "prospect-1", "sent": True},
    )
    assert register.status_code == 410
    assert touched.status_code == 410
