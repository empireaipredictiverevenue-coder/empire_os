"""The public lookup accepts one ZIP and NEVER grants a call route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os import lead_smart_public_coverage_api as api
from empire_os.lead_smart_homeowner_eligibility import PreviewEvidenceError

app = FastAPI()
app.include_router(api.router)
client = TestClient(app)


def _verified_preview():
    return {
        "schema_version": "empire.lead_smart.public_zip_preview.v1",
        "mode": "PREACTIVATION",
        "purpose": "COVERAGE_GUIDANCE_ONLY",
        "covered_zips": ["00501", "07728"],
        "count": 2,
        "expires_at": "2099-10-09T18:00:00+00:00",
        "call_authorized": False,
        "execution_authority": "NONE",
    }


@pytest.fixture(autouse=True)
def mock_data(monkeypatch):
    monkeypatch.setattr(api, "generate_from_files", lambda *args: _verified_preview())
    monkeypatch.setattr(
        api, "buyer_hours_preview",
        lambda: {"within_reported_window": True,
                 "timezone_interpretation_verified": False},
    )


@pytest.mark.parametrize(("zipcode", "expected"), [
    ("00501", "LISTED_IN_RECENT_COVERAGE"),
    ("07728", "LISTED_IN_RECENT_COVERAGE"),
    ("99999", "NOT_LISTED_IN_RECENT_COVERAGE"),
])
def test_public_zip_lookup_is_noncommercial_guidance_only(zipcode, expected):
    result = client.post("/roofing/coverage-check", json={"zip": zipcode})
    assert result.status_code == 200
    d = result.json()
    assert d["coverage_guidance"] == expected
    assert d["status"] == "GUIDANCE_ONLY"
    assert d["call_authorized"] is False
    assert d["buyer_route_verified"] is False
    assert d["time_zone_interpretation_verified"] is False
    assert d["execution_authority"] == "NONE"
    assert result.headers["cache-control"].startswith("no-store")
    assert result.headers["x-robots-tag"] == "noindex, nofollow"
    assert result.headers["referrer-policy"] == "no-referrer"
    assert "covered_zips" not in d
    assert "top_payout" not in d
    assert "tracking_number" not in d
    assert "call_number" not in d
    assert "00501" not in result.text


@pytest.mark.parametrize("request_body", [
    {"zip": 501},
    {"zip": "501"},
    {"zip": "00501 "},
    {"zip": "0a501"},
    {"zip": "00501", "caller_number": "+12125550123"},
    {},
    [],
])
def test_public_zip_endpoint_rejects_bad_or_extra_inputs(request_body):
    result = client.post("/roofing/coverage-check", json=request_body)
    assert result.status_code == 422


def test_expired_or_missing_evidence_fails_closed(monkeypatch):
    def fail(*args):
        raise PreviewEvidenceError("source stale")
    monkeypatch.setattr(api, "generate_from_files", fail)
    result = client.post("/roofing/coverage-check", json={"zip": "00501"})
    assert result.status_code == 503
    assert result.json() == {
        "schema_version": "empire.lead_smart.zip_check_response.v1",
        "status": "UNAVAILABLE",
        "call_authorized": False,
        "execution_authority": "NONE",
    }
    assert "source stale" not in result.text
    assert result.headers["cache-control"].startswith("no-store")


def test_gateway_registers_public_zip_lookup():
    # FastAPI may retain include_router as a lazy _IncludedRouter object;
    # exercise the real app rather than inspecting implementation internals.
    from empire_os.public_gateway import app as gateway_app
    result = TestClient(gateway_app).post(
        "/roofing/coverage-check", json={"zip": "00501"}
    )
    assert result.status_code == 200
    assert result.json()["coverage_guidance"] == "LISTED_IN_RECENT_COVERAGE"
    assert result.json()["call_authorized"] is False
