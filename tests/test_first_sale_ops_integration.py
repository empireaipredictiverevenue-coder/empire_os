"""Actual existing Ops Control cycle with new first-party proof sources offline."""
from __future__ import annotations

import json

from empire_os.first_sale_live_conversion_observer import (
    observe_first_sale_readiness,
)
from test_commercial_full_ops_cycle_sandbox import (
    _configure_sandbox, _load_ops,
)
from test_first_sale_live_conversion_observer import (
    owner_counts, checkout,
)


def test_ops_first_sale_new_enquiry_and_dedup_sandbox(tmp_path, monkeypatch, capsys):
    ops_module = _load_ops()
    ops_dir = _configure_sandbox(monkeypatch, ops_module, tmp_path)
    sources = {"enquiries": 0}

    def verified_sources(*, root, now, previous):
        return observe_first_sale_readiness(
            root=root, now=now, previous=previous,
            sales_probe=lambda: owner_counts(sources["enquiries"]),
            health_probe=checkout,
        )
    monkeypatch.setattr(ops_module, "observe_first_sale_readiness", verified_sources)
    for iteration, count, state in (
        (0, 0, "INITIAL_FIRST_SALE_BASELINE"),
        (1, 0, "UNCHANGED_FIRST_SALE_EVIDENCE_HOLD"),
        (2, 1, "FIRST_SALE_SOURCE_CHANGE_OWNER_REVIEW_REQUIRED"),
        (3, 1, "UNCHANGED_FIRST_SALE_EVIDENCE_HOLD"),
    ):
        sources["enquiries"] = count
        assert ops_module.main() == 0
        capsys.readouterr()
        data = json.loads((ops_dir / "latest.json").read_text())
        packet = data["first_sale_conversion_readiness"]
        assert packet["transition"] == state
        assert packet["canonical_sales_acquisition_counts"]["sales_acquisition_rows"] == count
        assert data["health_domains"]["first_sale_conversion"] == packet["status"]
        assert packet["verified_first_sale"] is None
        assert packet["recognized_revenue_cents"] is None
        assert packet["database_writes"] is False
        assert packet["payment_action"] is False
        assert packet["outbound_sent"] is False


def test_failed_canonical_source_does_not_break_existing_ops_or_claim_sales(
    tmp_path, monkeypatch, capsys,
):
    ops_module = _load_ops()
    ops_dir = _configure_sandbox(monkeypatch, ops_module, tmp_path)
    assert ops_module.main() == 0
    capsys.readouterr()
    state = json.loads((ops_dir / "latest.json").read_text())
    status = state["first_sale_conversion_readiness"]
    assert status["status"] == "FIRST_PARTY_CANONICAL_SOURCE_UNVERIFIED"
    assert status["canonical_sales_acquisition_counts"] is None
    assert status["old_funnel_counts_used_as_current"] is False
    assert state["adaptive_commercial_review"]["execution_authority"] == "none"
    assert state["health_domains"]["first_sale_conversion"] == status["status"]
    assert status["verified_first_sale"] is None
