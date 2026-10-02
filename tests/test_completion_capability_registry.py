from pathlib import Path

from empire_os.completion_capability_registry import (
    WORKSTREAMS,
    build_completion_capability_registry,
)

ROOT = Path(__file__).resolve().parents[1]


def test_registry_covers_full_completion_programme():
    payload = build_completion_capability_registry(ROOT)
    assert payload["workstream_count"] == 31
    keys = {row["key"] for row in payload["workstreams"]}
    for required in {
        "predictive_cloud_quant",
        "marketplace_auction",
        "revenue_exchange",
        "commercial_exchange",
        "digital_twin",
        "capital_allocator",
        "saas_network",
        "revenue_truth",
    }:
        assert required in keys


def test_registry_preserves_checklist_truth_and_live_reconciliation_gate():
    payload = build_completion_capability_registry(ROOT)
    assert payload["checklist"]["total"] >= 591
    assert payload["checklist"]["pending"] > 0
    assert all(row["runtime_reconciliation_required"] is True for row in payload["workstreams"])
    assert all(row["code_presence_is_not_completion"] is True for row in payload["workstreams"])


def test_marketplace_and_bidding_are_first_class():
    payload = build_completion_capability_registry(ROOT)
    row = next(row for row in payload["workstreams"] if row["key"] == "marketplace_auction")
    assert any(path.endswith("marketplace.py") for path in row["module_evidence"])
    assert any(path.endswith("opportunity_auction.py") for path in row["module_evidence"])
    assert row["state"] in {"PARTIAL", "CONNECTED"}


def test_registry_never_grants_consequential_authority():
    payload = build_completion_capability_registry(ROOT)
    authority = payload["authority"]
    assert authority["registry_execution_authority"] == "none"
    assert authority["live_outbound"] == "founder_gate"
    assert authority["binding_terms"] == "founder_gate"
    assert authority["funds_mainnet"] == "founder_gate"
    assert len(WORKSTREAMS) == 31
