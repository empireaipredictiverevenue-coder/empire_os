import json

from empire_os.rd_innovator_review import (
    LEGACY_INNOVATOR_PROPOSALS,
    SEED_FILE,
    review_innovator_rd_intake,
)


def _seed(tmp_path, proposals):
    file = tmp_path / SEED_FILE
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps({"proposals": proposals}), encoding="utf-8")


def test_rd_innovator_reuses_existing_roles_and_seed(tmp_path):
    _seed(tmp_path, [{
        "name": "National Storm Hub — Storm Passport and Atlas",
        "problem": "Help US homeowners prepare for storm seasons",
        "hypothesis": "An evidence-backed Atlas creates utility",
        "experiment": "Benchmark event provenance",
        "reuse_components": ["empire_os/storm_intelligence_runtime.py"],
    }])
    report = review_innovator_rd_intake(tmp_path)
    assert report["status"] == "REVIEW_READY"
    assert report["rd_owner"] == "rd_innovation"
    assert report["supervisor_owner"] == "strategy"
    assert report["innovator_role_registered_in_rd"] is True
    assert report["supervisor_role_registered_in_strategy"] is True
    assert report["founder_seed_count"] == 1
    assert report["legacy_seed_count"] == len(LEGACY_INNOVATOR_PROPOSALS)
    assert all(c["lifecycle_stage"] == "IDEA" for c in report["candidates"])
    assert all(c["ship_action"] is None for c in report["candidates"])
    assert all(c["financial_forecast"] is None for c in report["candidates"])
    assert report["queue_mutated"] is False
    assert report["model_invoked"] is False
    assert report["execution_authority"] == "none"
    assert not (tmp_path / "runtime").exists()


def test_rd_innovator_deduplicates_and_never_executes_injected_ship_action(tmp_path):
    _seed(tmp_path, [
        {"name": "Duplicated", "ship_action": {"kind": "send_email"}, "expected_revenue_usdt_monthly": 999999},
        {"name": "duplicated", "ship_action": {"kind": "restart_service"}},
        {"name": None},
        {"name": " "},
    ])
    report = review_innovator_rd_intake(tmp_path)
    assert report["founder_seed_count"] == 1
    candidate = next(c for c in report["candidates"] if c["name"] == "Duplicated")
    assert candidate["ship_action"] is None
    assert candidate["financial_forecast"] is None
    assert candidate["customer_actions_authorized"] is False


def test_rd_innovator_degrades_safely_on_missing_or_invalid_seed(tmp_path):
    report = review_innovator_rd_intake(tmp_path)
    assert report["seed_state"] == "ABSENT"
    assert report["status"] == "REVIEW_WITH_GAPS"
    assert report["candidate_count"] == len(LEGACY_INNOVATOR_PROPOSALS)
    file = tmp_path / SEED_FILE
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("{ bad json", encoding="utf-8")
    report = review_innovator_rd_intake(tmp_path)
    assert report["seed_state"] == "INVALID_SEED"
    assert report["execution_authority"] == "none"
