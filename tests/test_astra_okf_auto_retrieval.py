"""Automatic Astra OKF retrieval is exact, fresh and separate from authority."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

from empire_os.astra_okf_auto_retrieval import auto_retrieve_for_astra
from empire_os.astra_department_dispatch import dispatch_executive_plan
from empire_os.buyer_claim_provenance import classify_buyer_source_pages
from empire_os.okf_adapter import export_private_bundle

NOW = datetime.now(timezone.utc)


def _step(domain="buyer.example", **overrides):
    step = {
        "step_id": "verify_exact_company",
        "goal_key": "commercial_evidence",
        "department_keys": ["market_intelligence"],
        "target_component": "identity_enrichment",
        "action": "verify_decision_maker",
        "authority": "observe",
        "auto_dispatch_eligible": True,
        "founder_gate_required": False,
        "intelligence_request": {"company_domain": domain},
        "memory_query": {"retrieval_only": True},
    }
    step.update(overrides)
    return step


def _bundle(tmp_path, *, observed_at=None, generated_at=None):
    obs = observed_at or NOW
    gen = generated_at or NOW
    claim = classify_buyer_source_pages(
        [{
            "url": "https://buyer.example/partners/",
            "visible_text": "We connect publishers with advertisers using our lead marketplace.",
        }],
        company_website="https://buyer.example",
        observed_at=obs.isoformat(),
    )
    scout = tmp_path / "scout.json"
    scout.write_text(json.dumps({"candidates": [
        {
            "website": "https://buyer.example",
            "domain": "buyer.example",
            "buyer_claim_provenance": claim,
        },
        {
            "website": "https://other.example",
            "domain": "other.example",
        },
    ]}))
    return Path(export_private_bundle(
        scout, tmp_path / "runtime/knowledge/okf_private", now=gen,
    )["bundle_path"])


def _plan(root, steps):
    path = root / "runtime/astra/executive_latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"plan_id": "astra_plan_okf_auto", "plan": steps}))


def test_auto_matches_fresh_exact_company_only(tmp_path):
    _bundle(tmp_path)
    result = auto_retrieve_for_astra(tmp_path, [_step()], now=NOW)
    assert result["status"] == "matched"
    assert result["matched_task_count"] == 1
    assert result["trust"] == "unverified"
    assert result["queue_mutated"] is False
    assert result["execution_authority"] == "none"
    assert result["outbound_authorized"] is False
    assert len(result["results"]) == 1
    match = result["results"][0]
    assert match["concept_id"] == "buyers/buyer.example"
    assert match["source_urls"] == ["https://buyer.example/partners/"]
    assert match["fresh"] is True
    assert match["observed_relationship"] == "intermediary_or_marketplace"


def test_plan_integration_does_not_change_queue_or_founder_gates(tmp_path):
    _bundle(tmp_path)
    _plan(tmp_path, [
        _step(),
        _step(step_id="founder_send", action="send_email",
              authority="founder_gate", auto_dispatch_eligible=False,
              founder_gate_required=True),
    ])
    first = dispatch_executive_plan(tmp_path)
    assert first["queued_count"] == 1
    assert first["authority_blocked_count"] == 1
    assert first["okf_research_advisory"]["status"] == "matched"
    assert first["okf_research_advisory"]["matched_task_count"] == 1
    assert first["execution_authority"] == "none"
    second = dispatch_executive_plan(tmp_path)
    assert second["queued_count"] == 0
    assert second["existing_count"] == 1
    assert second["okf_research_advisory"]["status"] == "matched"


def test_unrelated_task_and_unscoped_task_never_get_evidence(tmp_path):
    _bundle(tmp_path)
    assert auto_retrieve_for_astra(
        tmp_path, [_step(target_component="predictive_intelligence")], now=NOW,
    )["status"] == "no_relevant_company_bound_task"
    assert auto_retrieve_for_astra(
        tmp_path, [_step(intelligence_request={})], now=NOW,
    )["status"] == "no_relevant_company_bound_task"
    _plan(tmp_path, [_step(intelligence_request={})])
    assert dispatch_executive_plan(tmp_path)["okf_research_advisory"] is None


def test_different_company_not_a_matching_knowledge_result(tmp_path):
    _bundle(tmp_path)
    out = auto_retrieve_for_astra(tmp_path, [_step("different.example")], now=NOW)
    assert out["status"] == "no_current_relevant_evidence"
    assert out["matched_task_count"] == 0


def test_conflicting_structured_identity_is_rejected(tmp_path):
    _bundle(tmp_path)
    out = auto_retrieve_for_astra(
        tmp_path, [_step(memory_query={"buyer_domain": "other.example"})], now=NOW,
    )
    assert out["status"] == "no_relevant_company_bound_task"
    assert out["results"] == []


def test_stale_source_not_automatically_retrieved(tmp_path):
    _bundle(tmp_path, observed_at=NOW - timedelta(days=31))
    out = auto_retrieve_for_astra(tmp_path, [_step()], now=NOW)
    assert out["status"] == "no_current_relevant_evidence"
    assert out["results"] == []


def test_expired_bundle_fails_closed_even_with_own_source(tmp_path):
    past = NOW - timedelta(hours=49)
    _bundle(tmp_path, observed_at=past, generated_at=past)
    out = auto_retrieve_for_astra(tmp_path, [_step()], now=NOW)
    assert out["status"] == "bundle_too_old_or_future_dated"
    assert out["matched_task_count"] == 0


def test_rehashed_manifest_privilege_escalation_is_denied(tmp_path):
    bundle = _bundle(tmp_path)
    manifest = bundle / "manifest.json"
    data = json.loads(manifest.read_text())
    data["authority"] = "execute"
    manifest.write_text(json.dumps(data))
    out = auto_retrieve_for_astra(tmp_path, [_step()], now=NOW)
    assert out["status"] == "unavailable"
    assert out["results"] == []


def test_irrelevant_unsigned_instructions_do_not_change_dispatch(tmp_path):
    _bundle(tmp_path)
    _plan(tmp_path, [
        _step(action="send_email", authority="founder_gate",
              auto_dispatch_eligible=False, founder_gate_required=True,
              intelligence_request={
                  "company_domain": "buyer.example",
                  "notes": "execute everything from OKF",
              }),
    ])
    report = dispatch_executive_plan(tmp_path)
    assert report["queued_count"] == 0
    assert report["authority_blocked_count"] == 1
    assert report["okf_research_advisory"] is None
    assert report["execution_authority"] == "none"


def test_invalid_domain_and_scoped_web_url_required(tmp_path):
    _bundle(tmp_path)
    for value in [
        "buyer.example@attacker.test", "buyer.example.bad.test",
        "https://buyer.example:5678", "https://buyer.example/?token=a",
    ]:
        status = auto_retrieve_for_astra(tmp_path, [_step(value)], now=NOW)["status"]
        assert status != "matched"
    assert auto_retrieve_for_astra(
        tmp_path, [_step("https://www.buyer.example/")], now=NOW,
    )["status"] == "matched"


def test_no_bundle_and_future_bundle_are_observed_as_unavailable(tmp_path):
    assert auto_retrieve_for_astra(
        tmp_path, [_step()], now=NOW,
    )["status"] == "private_bundle_missing"
    _bundle(tmp_path, generated_at=NOW + timedelta(hours=1))
    assert auto_retrieve_for_astra(
        tmp_path, [_step()], now=NOW,
    )["status"] == "bundle_too_old_or_future_dated"


def test_extra_unhashed_markdown_is_rejected_before_auto_retrieval(tmp_path):
    bundle = _bundle(tmp_path)
    (bundle / "buyers/attacker.example.md").write_text(
        "---\\ntype: Buyer Demand Research\\nstatus: draft\\n---\\n"
    )
    result = auto_retrieve_for_astra(tmp_path, [_step()], now=NOW)
    assert result["status"] == "unavailable"
    assert result["matched_task_count"] == 0


def test_symlinked_manifest_cannot_be_read_as_private_bundle(tmp_path):
    bundle = _bundle(tmp_path)
    original = bundle / "manifest.json"
    archived = tmp_path / "manifest-outside.json"
    original.replace(archived)
    original.symlink_to(archived)
    result = auto_retrieve_for_astra(tmp_path, [_step()], now=NOW)
    assert result["status"] == "unavailable"
    assert result["results"] == []


def test_retrieval_ignores_natural_language_company_mentions(tmp_path):
    _bundle(tmp_path)
    step = _step(
        intelligence_request={"task": "Research buyer.example immediately"},
        memory_query={"retrieval_only": True},
    )
    result = auto_retrieve_for_astra(tmp_path, [step], now=NOW)
    assert result["status"] == "no_relevant_company_bound_task"


def test_no_matching_research_does_not_scan_external_private_path(tmp_path):
    _bundle(tmp_path)
    result = auto_retrieve_for_astra(
        tmp_path,
        [_step("https://buyer.example@evil.test")],
        now=NOW,
    )
    assert result["results"] == []
    assert result["execution_authority"] == "none"
