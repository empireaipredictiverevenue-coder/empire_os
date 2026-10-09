"""Flow meter must be emitted by the existing review cycle without changing authority."""
import json
import sys

import scripts.materialize_buyer_scout_review_readiness as runner


def test_scheduled_review_worker_emits_flow_observation(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["review", "--repo-root", "/tmp/test-empire"])
    monkeypatch.setattr(runner, "_audit_stale_ready", lambda **kwargs: {
        "mismatch_ids": [], "quarantined_count": 0,
        "database_write_performed": False,
    })
    monkeypatch.setattr(runner, "request_json", lambda *args, **kwargs: [])
    monkeypatch.setattr(runner, "materialize_review_readiness", lambda *args, **kwargs: {
        "candidate_count": 3, "review_ready_count": 0, "blocked_count": 3,
        "database_write_performed": False,
    })
    monkeypatch.setattr(runner, "write_review_readiness", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "refresh_evidence_quality_scorecard", lambda *args: {
        "scout_candidate_count": 2,
        "stage_receipts_time_aligned": True,
        "scout_receipt_fresh": True,
        "candidate_with_valid_direct_purchase_receipt": 0,
        "candidate_with_strict_named_person_email_binding": 0,
    })
    observed = []
    def flow_stub(root):
        observed.append(root)
        return {
            "health_checks": {
                "scout_fresh": True,
                "scout_to_reconciliation_verified": True,
                "evidence_quality_aligned": True,
                "review_fresh": True,
                "revenue_truth_fresh": True,
                "commercial_truth_fresh": False,
            },
            "handoffs": {"scout_to_reconciliation": {"joined_count": 2}},
            "stages": {
                "holding_review_scanned": {"current_count": 3},
                "astra_canonical_bindings": {"current_count": 0},
            },
        }
    monkeypatch.setattr(runner, "refresh_flow_meter", flow_stub)
    assert runner.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert observed == ["/tmp/test-empire"]
    assert out["flow_meter_status"] == "upstream_current_downstream_stale"
    assert out["flow_meter_summary"]["scout_domain_join_count"] == 2
    assert out["flow_meter_summary"]["commercial_funnel_current"] is False
    assert out["canonical_promotion_performed"] is False
    assert out["outbound_sent"] is False
    assert out["execution_authority"] == "none"


def test_optional_flow_meter_failure_does_not_bypass_review_gate(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["review", "--observe-only"])
    monkeypatch.setattr(runner, "_audit_stale_ready", lambda **kwargs: {
        "mismatch_ids": [], "quarantined_count": 0,
        "database_write_performed": False,
    })
    monkeypatch.setattr(runner, "request_json", lambda *args, **kwargs: [])
    monkeypatch.setattr(runner, "materialize_review_readiness", lambda *args, **kwargs: {
        "candidate_count": 0, "review_ready_count": 0, "blocked_count": 0,
        "database_write_performed": False,
    })
    monkeypatch.setattr(runner, "write_review_readiness", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "refresh_evidence_quality_scorecard", lambda *args: {
        "scout_candidate_count": 0,
        "stage_receipts_time_aligned": False,
        "scout_receipt_fresh": False,
        "candidate_with_valid_direct_purchase_receipt": 0,
        "candidate_with_strict_named_person_email_binding": 0,
    })
    def fail(root):
        raise ValueError("tampered meter history")
    monkeypatch.setattr(runner, "refresh_flow_meter", fail)
    assert runner.main() == 0
    stdout = capsys.readouterr().out
    assert "REVENUE_FLOW_METER_UNAVAILABLE:ValueError" in stdout
    end = json.loads(stdout[stdout.index("{"):])
    assert end["flow_meter_status"] == "unavailable"
    assert end["outbound_sent"] is False
    assert end["canonical_promotion_performed"] is False
