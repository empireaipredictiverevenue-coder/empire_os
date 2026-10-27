"""The original unprivileged pulse can never prove a payable sale."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pytest

from empire_os.commercial_buyer_source_health import inspect_existing_lead_smart_cash_pulse

NOW = datetime(2026, 10, 27, 14, tzinfo=timezone.utc)


def record():
    return {
        "schema_version": "empire.lead_smart.commercial_pulse.v1",
        "buyer": "Lead Smart", "site_route": "/roofing",
        "campaign_id": "CA8278ed3f26e9495b881fe3833174d007",
        "observed_at_utc": (NOW - timedelta(minutes=10)).isoformat(),
        "site_handoffs_recorded": 0,
        "site_handoff_switch_enabled": False,
        "no_real_revenue_inferred_from_tracking": True,
        "settled_revenue_verified": False,
        "qualified_billable_calls_verified": False,
        "actual_connected_homeowner_calls_verified": False,
        "raw_call_identifiers_persisted": False,
        "ringba": {
            "matching_rows_in_returned_window": 2,
            "provider_token_read_by_unprivileged_process": False,
            "payable_call_verified": False,
            "settled_revenue_verified": False,
            "buyer_leg_connected_verified": False,
            "raw_call_id": "SECRET_ID_MUST_NOT_EXPORT",
        },
        "private_caller": "HIDDEN_PRIVATE_CALLER",
    }


def snapshot(tmp_path, data=None):
    p = tmp_path / "runtime/revenue/lead_smart/commercial_pulse/latest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data if data is not None else record()))
    return p


def test_original_ringba_two_rows_and_disabled_handoff_never_become_revenue(tmp_path):
    p = snapshot(tmp_path)
    contents = p.read_bytes()
    result = inspect_existing_lead_smart_cash_pulse(tmp_path, now=NOW)
    assert p.read_bytes() == contents
    assert result["status"] == "NO_CONFIRMED_PAYABLE_CALL_FROM_UNPRIVILEGED_OWNER_PULSE"
    assert result["site_handoffs"] == 0
    assert result["provider_row_count"] == 2
    assert result["site_handoff_switch_enabled"] is False
    assert result["settled_revenue_cents"] is None
    assert result["predictive_cloud_calibration_authorized"] is False
    assert result["provider_accepted_calls_claimed"] is None
    assert "HIDDEN_PRIVATE_CALLER" not in str(result)
    assert "SECRET_ID_MUST_NOT_EXPORT" not in str(result)


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(settled_revenue_verified=True),
    lambda x: x.update(qualified_billable_calls_verified=True),
    lambda x: x["ringba"].update(payable_call_verified=True),
    lambda x: x["ringba"].update(provider_token_read_by_unprivileged_process=True),
    lambda x: x.update(site_handoffs_recorded=-1),
    lambda x: x.update(site_handoff_switch_enabled="yes"),
    lambda x: x.update(campaign_id="unauthorized-campaign"),
])
def test_untrusted_source_does_not_claim_sales(tmp_path, mutation):
    d = record()
    mutation(d)
    snapshot(tmp_path, d)
    r = inspect_existing_lead_smart_cash_pulse(tmp_path, now=NOW)
    assert r["status"] == "ORIGINAL_LEAD_SMART_PULSE_UNAVAILABLE"
    assert r["settled_revenue_cents"] is None
    assert r["predictive_cloud_calibration_authorized"] is False


def test_stale_or_absent_owner_evidence_unknown_not_zero(tmp_path):
    assert inspect_existing_lead_smart_cash_pulse(tmp_path, now=NOW)["site_handoffs"] is None
    x = record()
    x["observed_at_utc"] = (NOW - timedelta(days=2)).isoformat()
    snapshot(tmp_path, x)
    r = inspect_existing_lead_smart_cash_pulse(tmp_path, now=NOW)
    assert r["source_freshness"] == "INVALID_OR_STALE"
    assert r["provider_row_count"] is None


def test_unprivileged_operator_cannot_downgrade_protected_owner_file(tmp_path):
    snapshot(tmp_path)
    protected = tmp_path / "runtime/revenue/lead_smart/commercial_pulse/call_to_cash_latest.json"
    protected.write_text(json.dumps({"private_test_id": "DO_NOT_READ"}))
    result = inspect_existing_lead_smart_cash_pulse(tmp_path, now=NOW)
    assert result["protected_call_to_cash_receipt"] == "UNTRUSTED_PROTECTED_RECEIPT_METADATA"
    assert "DO_NOT_READ" not in str(result)
