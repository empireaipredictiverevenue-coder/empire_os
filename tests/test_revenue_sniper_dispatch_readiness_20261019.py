"""Three distinct existing production populations, one no-write readiness view."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.revenue_sniper_dispatch_readiness import (
    build_sniper_dispatch_readiness,
)
from scripts.review_revenue_sniper_dispatch_readiness_20261019 import main

NOW = datetime(2026, 10, 19, 12, 30, tzinfo=timezone.utc)


def receipts():
    scout = {
        "schema_version": "empire.buyer_acquisition_scout.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "database_write_performed": False, "outbound_sent": False,
        "generated_at": NOW.isoformat(), "queries": [],
        "candidates": [{
            "domain": "firm.example",
            "continuous_commercial_lane": "predictive_revenue_enterprise",
            "discovery_source": "public_research_seed",
            "candidate_state": "RESEARCH_EVIDENCE_ONLY",
            "outreach_authorized": False,
            "buyer_type": "unknown",
            "canonical_identity_verified": False,
            "budget_verified": False,
            "commercial_terms_verified": False,
            "direct_buyer_score": 0,
            "decision_maker_state": "OBSERVED_ROLE_MATCH",
            "economic_capacity_state": "UNKNOWN",
        }],
    }
    review = {
        "schema_version": "empire.buyer_scout_review_readiness.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "database_write_performed": False, "outbound_sent": False,
        "canonical_promotion_performed": False,
        "generated_at": NOW.isoformat(),
        "candidate_count": 7, "review_ready_count": 0,
        "blocked_count": 7,
        "blocked_reason_counts": {
            "site_evidence_below_floor": 3,
            "direct_buyer_evidence_missing": 2,
            "official_registry_identity_mismatch": 2,
        },
    }
    exchange = {
        "schema_version": "empire.commercial_exchange_snapshot.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "source": "canonical_empiredb_projection",
        "canonical_backend": "empiredb",
        "automatic_external_delivery": False,
        "observed_at": NOW.isoformat(),
        "buyer_seat_count": 5,
        "seat_state_counts": {"blocked_missing_evidence": 5},
        "inventory_count": 3, "allocated_count": 0,
    }
    return scout, review, exchange


def run(**override):
    s, r, e = receipts()
    return build_sniper_dispatch_readiness(
        scout_snapshot=override.get("scout", s),
        buyer_review_snapshot=override.get("review", r),
        commercial_exchange_snapshot=override.get("exchange", e),
        now=override.get("now", NOW),
    )


def test_three_scopes_remain_independent_and_no_authority():
    out = run()
    assert out["state"] == "INTERNAL_RESEARCH_READY"
    assert out["scout"]["research_rows"] == 1
    assert out["buyer_review"]["assessed_records"] == 7
    assert out["empiredb_exchange"]["buyer_seat_records"] == 5
    assert out["empiredb_exchange"]["active_capacity_seat_records"] == 0
    assert out["buyer_review"]["distinct_population_not_scout_candidates"] is True
    assert out["empiredb_exchange"]["independent_population_not_scanner_observations"] is True
    assert out["priority_human_work"]
    assert not out["verified_buyer_delivery_available"]
    assert not out["outreach_authorized"]
    assert not out["canonical_empiredb_writes"]


@pytest.mark.parametrize("which,key,value", [
    ("scout", "outbound_sent", True),
    ("review", "database_write_performed", True),
    ("review", "canonical_promotion_performed", True),
    ("exchange", "canonical_backend", "supabase"),
    ("exchange", "automatic_external_delivery", True),
])
def test_untrusted_execution_or_database_contracts_hold(which, key, value):
    s, r, e = receipts()
    obj = {"scout": s, "review": r, "exchange": e}[which]
    obj[key] = value
    if which == "scout":
        with pytest.raises(ValueError):
            run(scout=s)
    else:
        out = run(review=r, exchange=e)
        assert out["state"] == "HOLD_EVIDENCE"
        assert out["hold_reasons"]
        assert not out["outreach_authorized"]


def test_stale_review_snapshot_fails_closed():
    s, r, e = receipts()
    r["generated_at"] = (NOW - timedelta(hours=7)).isoformat()
    out = run(review=r)
    assert out["state"] == "HOLD_EVIDENCE"
    assert "buyer_review_snapshot_stale" in out["hold_reasons"]


def test_stale_exchange_snapshot_fails_closed():
    s, r, e = receipts()
    e["observed_at"] = (NOW - timedelta(hours=7)).isoformat()
    out = run(exchange=e)
    assert out["state"] == "HOLD_EVIDENCE"
    assert "exchange_snapshot_stale" in out["hold_reasons"]


def test_mismatched_seat_totals_hold():
    s, r, e = receipts()
    e["seat_state_counts"] = {"blocked_missing_evidence": 4}
    out = run(exchange=e)
    assert "seat_count_mismatch" in out["hold_reasons"]


def test_review_blocker_counts_cannot_be_partial():
    s, r, e = receipts()
    r["blocked_reason_counts"]["site_evidence_below_floor"] = 1
    out = run(review=r)
    assert "buyer_blocker_totals_do_not_reconcile" in out["hold_reasons"]


def test_review_unreconciled_review_ready_is_hold():
    s, r, e = receipts()
    r["review_ready_count"] = 3
    out = run(review=r)
    assert "buyer_review_totals_do_not_reconcile" in out["hold_reasons"]


def test_rejected_bool_counts_and_missing_timestamps_hold():
    s, r, e = receipts()
    r["candidate_count"] = True
    e["observed_at"] = None
    out = run(review=r, exchange=e)
    assert "required_counter_missing" in out["hold_reasons"]
    assert "exchange_snapshot_stale" in out["hold_reasons"]


def test_cli_local_only_reads_three_snapshots(tmp_path, capsys):
    s, r, e = receipts()
    current = datetime.now(timezone.utc).isoformat()
    s["generated_at"] = current
    r["generated_at"] = current
    e["observed_at"] = current
    paths = []
    for name, payload in (("scout", s), ("review", r), ("exchange", e)):
        p = tmp_path / (name + ".json")
        p.write_text(json.dumps(payload))
        paths.append(p)
    assert main([
        "--read-only", "--scout", str(paths[0]),
        "--review", str(paths[1]), "--exchange", str(paths[2]),
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "INTERNAL_RESEARCH_READY"
    assert result["empiredb_exchange"]["blocked_missing_evidence_seat_records"] == 5
    assert all(path.exists() for path in paths)


def test_cli_invalid_json_no_leak(tmp_path, capsys):
    paths = []
    for name in ("scout", "review", "exchange"):
        p = tmp_path / (name + ".json")
        p.write_text("private customer data malformed")
        paths.append(p)
    assert main([
        "--read-only", "--scout", str(paths[0]),
        "--review", str(paths[1]), "--exchange", str(paths[2]),
    ]) == 2
    out = capsys.readouterr().out
    assert "private customer" not in out
    assert json.loads(out)["execution_authority"] == "none"
