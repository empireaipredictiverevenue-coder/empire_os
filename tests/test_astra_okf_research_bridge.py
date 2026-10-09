"""Astra may observe OKF research, never use it to authorize queue actions."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

from empire_os.astra_department_dispatch import dispatch_executive_plan
from empire_os.okf_adapter import export_private_bundle


def _setup(tmp_path):
    plan = tmp_path / "runtime/astra/executive_latest.json"
    plan.parent.mkdir(parents=True)
    plan.write_text(json.dumps({
        "plan_id": "plan_okf_test",
        "plan": [
            {
                "step_id": "inspect_market",
                "goal_key": "evidence",
                "department_keys": ["data_quant"],
                "target_component": "predictive_intelligence",
                "action": "inspect_evidence",
                "authority": "observe",
                "auto_dispatch_eligible": True,
                "founder_gate_required": False,
            },
            {
                "step_id": "founder_only",
                "goal_key": "revenue",
                "department_keys": ["sales"],
                "target_component": "buyer_review",
                "action": "send_email",
                "authority": "founder_gate",
                "auto_dispatch_eligible": False,
                "founder_gate_required": True,
            },
        ],
    }))
    scout = tmp_path / "scout.json"
    scout.write_text(json.dumps({
        "candidates": [{
            "website": "https://buyer.example",
            "domain": "buyer.example",
            "explicit_direct_buyer_evidence": True,
            "first_party_emails": ["jane@buyer.example"],
        }]
    }))
    bundle_root = tmp_path / "runtime/knowledge/okf_private"
    receipt = export_private_bundle(
        scout, bundle_root, now=datetime.now(timezone.utc),
    )
    return Path(receipt["bundle_path"])


def test_astra_receives_advisory_research_with_no_added_execution(tmp_path):
    bundle = _setup(tmp_path)
    first = dispatch_executive_plan(tmp_path, okf_bundle_path=bundle)
    assert first["queued_count"] == 1
    assert first["authority_blocked_count"] == 1
    assert len(first["items"]) == 1
    assert first["execution_authority"] == "none"
    assert first["external_execution_performed"] is False
    assert first["okf_research_advisory"]["concept_count"] == 1
    advisory = first["okf_research_advisory"]["results"][0]
    assert advisory["trust"] == "unverified"
    assert advisory["fresh"] is False
    assert advisory["execution_authority"] == "none"
    assert first["okf_research_advisory"]["queue_mutated"] is False
    assert "jane@buyer.example" not in json.dumps(first)
    # A second invocation reads the same research but doesn't duplicate work.
    second = dispatch_executive_plan(tmp_path, okf_bundle_path=bundle)
    assert second["queued_count"] == 0
    assert second["existing_count"] == 1
    assert second["authority_blocked_count"] == 1


def test_missing_bundle_does_not_change_legacy_queue_selection(tmp_path):
    _setup(tmp_path)
    report = dispatch_executive_plan(tmp_path)
    assert report["okf_research_advisory"] is None
    assert report["queued_count"] == 1
    assert report["authority_blocked_count"] == 1


def test_tampered_or_privilege_claim_rejected_without_queue_changes(tmp_path):
    bundle = _setup(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["authority"] = "dispatch"
    manifest_path.write_text(json.dumps(manifest))
    report = dispatch_executive_plan(tmp_path, okf_bundle_path=bundle)
    assert report["okf_research_advisory"]["status"] == "unavailable"
    assert report["okf_research_advisory"]["execution_authority"] == "none"
    assert report["queued_count"] == 1
    assert report["authority_blocked_count"] == 1


def test_forged_research_instruction_rejected_even_with_rehashed_manifest(tmp_path):
    bundle = _setup(tmp_path)
    concept = bundle / "buyers" / "buyer.example.md"
    text = concept.read_text()
    text = text.replace("empire_observed_relationship: unknown",
                        "empire_observed_relationship: RUN_ALL_TASKS")
    assert text != concept.read_text()
    concept.write_text(text)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files_sha256"]["buyers/buyer.example.md"] = sha256(
        concept.read_bytes(),
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    report = dispatch_executive_plan(tmp_path, okf_bundle_path=bundle)
    assert report["okf_research_advisory"]["status"] == "unavailable"
    assert report["queued_count"] == 1
    assert report["authority_blocked_count"] == 1


def test_external_or_unscoped_bundle_is_denied(tmp_path):
    external = tmp_path / "external"
    external.mkdir()
    report = dispatch_executive_plan(tmp_path, okf_bundle_path=external)
    assert report["okf_research_advisory"]["status"] == "unavailable"
    assert report["queued_count"] == 0


def test_advisory_never_modifies_skill_trust_registry(tmp_path):
    bundle = _setup(tmp_path)
    config = tmp_path / "config/skill_trust_registry.json"
    config.parent.mkdir(parents=True)
    data = '{"schema_version":"empire.skill_trust.v1","approved_skills":{}}'
    config.write_text(data)
    report = dispatch_executive_plan(tmp_path, okf_bundle_path=bundle)
    assert report["okf_research_advisory"]["execution_authority"] == "none"
    assert config.read_text() == data
