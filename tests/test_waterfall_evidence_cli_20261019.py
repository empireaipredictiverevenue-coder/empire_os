"""Offline operator CLI proof: no operational side effects or access grants."""
import json
from datetime import datetime, timezone
from hashlib import sha256

from scripts.review_vertical_waterfall_evidence_20261019 import main


def source_report():
    return {
        "schema_version": "empire.scrapling_source_evidence.v1",
        "mode": "OFFLINE_REVIEW_ONLY",
        "source_id": "gb_companies_house",
        "source_url": "https://api.company-information.service.gov.uk/",
        "review_evidence_refs": ["terms:synthetic", "robots:synthetic", "privacy:synthetic"],
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "content_sha256": sha256(b"synthetic").hexdigest(),
        "records": [{
            "business_name": "Example Firm Ltd",
            "source_id": "gb_companies_house",
            "source_url": "https://api.company-information.service.gov.uk/",
            "niche_observed": "legal",
            "quality": "unverified_source_observation",
            "canonical_prospect_id": None,
            "commercial_resale_authorized": False,
        }],
        "live_network_access": False,
        "canonical_empiredb_writes": False,
        "sellable_inventory_verified": False,
    }


def test_cli_requires_independent_legal_policy(tmp_path, capsys):
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(source_report()))
    args = [
        "--read-only", "--report", str(path),
        "--vertical", "legal", "--target-kind", "law_firm",
        "--jurisdiction", "GB-ENG",
        "--company-identity-ref", "entity:synthetic-001",
    ]
    assert main(args) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["state"] == "HOLD"
    assert out["provider_order_review_only"] == []
    assert out["contact_promotion_authorized"] is False
    assert main(args + [
        "--jurisdiction-policy-ref", "compliance:synthetic-20261019"
    ]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["state"] == "EVIDENCE_REVIEW_READY"
    assert out["provider_order_review_only"] == ["registry_scraper"]
    assert out["provider_execution_authorized"] is False
    assert out["outbound_authorized"] is False


def test_cli_bad_json_never_echoes_source_content(tmp_path, capsys):
    path = tmp_path / "untrusted.json"
    path.write_text("{<private source info>")
    assert main([
        "--read-only", "--report", str(path), "--vertical", "insurance",
        "--target-kind", "insurance_broker", "--jurisdiction", "GB-ENG",
    ]) == 2
    msg = capsys.readouterr().out
    assert "private source info" not in msg
    assert json.loads(msg)["execution_authority"] == "none"
