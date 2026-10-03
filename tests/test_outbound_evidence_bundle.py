from datetime import datetime, timedelta, timezone

import pytest

from empire_os.outbound_evidence_bundle import (
    load_evidence_bundle,
    project_bundle_to_ringleader,
)
from empire_os.outbound_evidence_bundle_auth import sign_evidence_bundle


NOW = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)


def write_bundle(path, *, generated_at=None, sources=None, mutation=False):
    import json
    path.write_text(json.dumps({
        "schema_version": "1",
        "generated_at": (generated_at or NOW).isoformat(),
        "sources": sources or {},
        "mutation_authorized": mutation,
    }), encoding="utf-8")


def test_current_bundle_projects_open_source_and_seed_evidence(tmp_path):
    path = tmp_path / "evidence.json"
    write_bundle(path, sources={
        "checkdmarc": {
            "domain": "example.com",
            "spf": {"valid": True},
            "dmarc": {"valid": True},
        },
        "dnscontrol_preview": [],
        "seed_placement": {
            "measured": True,
            "inbox_placement_rate": 0.97,
        },
    })
    bundle = load_evidence_bundle(path, now=NOW)
    projected = project_bundle_to_ringleader(bundle)
    assert bundle["status"] == "CURRENT"
    assert projected["context"]["placement"]["measured"] is True
    assert "checkdmarc" in projected["context"]["open_source_evidence"]
    assert projected["mutation_authorized"] is False


def test_stale_bundle_is_not_projected(tmp_path):
    path = tmp_path / "evidence.json"
    write_bundle(
        path,
        generated_at=NOW - timedelta(hours=2),
        sources={"checkdmarc": {"domain": "example.com"}},
    )
    bundle = load_evidence_bundle(path, now=NOW, max_age_minutes=30)
    projected = project_bundle_to_ringleader(bundle)
    assert bundle["status"] == "STALE"
    assert projected["context"] == {}


def test_bundle_cannot_authorize_mutation(tmp_path):
    path = tmp_path / "evidence.json"
    write_bundle(path, mutation=True)
    with pytest.raises(RuntimeError, match="cannot_authorize_mutation"):
        load_evidence_bundle(path, now=NOW)


def test_unknown_source_is_ignored_and_reported(tmp_path):
    path = tmp_path / "evidence.json"
    write_bundle(path, sources={
        "mystery_vendor": {"x": 1},
        "parsedmarc": {"domain": "example.com", "records": []},
    })
    bundle = load_evidence_bundle(path, now=NOW)
    assert bundle["ignored_sources"] == ["mystery_vendor"]
    assert "unsupported_sources_ignored" in bundle["warnings"]
    assert "parsedmarc" in bundle["sources"]


def test_missing_bundle_is_safe_absence(tmp_path):
    bundle = load_evidence_bundle(tmp_path / "missing.json", now=NOW)
    assert bundle["status"] == "ABSENT"
    assert bundle["mutation_authorized"] is False



def test_required_signature_accepts_valid_empire_signed_bundle(tmp_path):
    import json

    key = "empire-test-signing-key-123456"
    bundle = sign_evidence_bundle({
        "schema_version": "1",
        "generated_at": NOW.isoformat(),
        "sources": {"parsedmarc": {"domain": "example.com", "records": []}},
        "mutation_authorized": False,
    }, key=key)
    path = tmp_path / "signed.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    loaded = load_evidence_bundle(
        path,
        now=NOW,
        hmac_key=key,
        require_signature=True,
    )
    assert loaded["signature_status"] == "VERIFIED"


def test_required_signature_rejects_unsigned_bundle(tmp_path):
    path = tmp_path / "unsigned.json"
    write_bundle(path)
    with pytest.raises(RuntimeError, match="signature_required"):
        load_evidence_bundle(
            path,
            now=NOW,
            hmac_key="empire-test-signing-key-123456",
            require_signature=True,
        )
