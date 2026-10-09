"""OKF research is visible to SkillForge but never promoted to executable skills."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

from empire_os.okf_adapter import export_private_bundle
from empire_os.skillforge import catalogue


def sample_bundle(tmp_path):
    record = tmp_path / "scout.json"
    record.write_text(json.dumps({"candidates": [
        {
            "website": "https://buyer.example",
            "domain": "buyer.example",
            "explicit_direct_buyer_evidence": True,
            "first_party_emails": ["jane@buyer.example"],
        },
    ]}))
    return Path(export_private_bundle(
        record, tmp_path / "okf", now=datetime.now(timezone.utc),
    )["bundle_path"])


def test_skillforge_advisory_research_is_not_a_skill(tmp_path):
    bundle = sample_bundle(tmp_path)
    result = catalogue(root=tmp_path / "skills", okf_bundle_path=bundle)
    research = result["okf_research"]
    assert research["concept_count"] == 1
    assert research["results"][0]["trust"] == "unverified"
    assert research["results"][0]["execution_authority"] == "none"
    assert research["results"][0]["fresh"] is False
    assert result["skill_count"] == 0
    assert result["approved_count"] == 0
    assert result["execution_authority"] == "none"
    assert "jane@buyer.example" not in json.dumps(research)


def test_corrupt_or_escalated_manifest_remains_unavailable(tmp_path):
    bundle = sample_bundle(tmp_path)
    manifest_file = bundle / "manifest.json"
    manifest = json.loads(manifest_file.read_text())
    manifest["authority"] = "execute"
    manifest_file.write_text(json.dumps(manifest))
    result = catalogue(root=tmp_path / "skills", okf_bundle_path=bundle)
    assert result["okf_research"]["status"] == "unavailable"
    assert result["okf_research"]["execution_authority"] == "none"
    assert result["approved_count"] == 0


def test_forged_review_with_matching_manifest_hash_still_blocked(tmp_path):
    bundle = sample_bundle(tmp_path)
    file = bundle / "buyers" / "buyer.example.md"
    content = file.read_text().replace("status: draft", "status: stable")
    file.write_text(content)
    manifest_file = bundle / "manifest.json"
    manifest = json.loads(manifest_file.read_text())
    manifest["files_sha256"]["buyers/buyer.example.md"] = sha256(
        file.read_bytes(),
    ).hexdigest()
    manifest_file.write_text(json.dumps(manifest))
    result = catalogue(root=tmp_path / "skills", okf_bundle_path=bundle)
    assert result["okf_research"]["status"] == "unavailable"
    assert result["approved_count"] == 0


def test_skillforge_default_inventory_does_not_load_okf(tmp_path):
    result = catalogue(root=tmp_path / "skills")
    assert result["okf_research"] is None
    assert result["execution_authority"] == "none"
