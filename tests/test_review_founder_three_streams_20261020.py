"""Three-chat owner control remains based on verified original Ops sources."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from scripts.review_founder_three_streams_20261020 import (
    SCHEMA, build_checkpoint, main,
)

NOW = datetime(2026, 10, 20, 17, 15, tzinfo=timezone.utc)


def original_ops(*, enquiry_count=0, asset_held=True, healthy=True):
    return {
        "schema_version": "empire.ops_control_cycle.v1",
        "mode": "OBSERVE",
        "observed_at": (NOW-timedelta(minutes=2)).isoformat(),
        "healthy": healthy,
        "private_email": "must-not-leak@example.invalid",
        "first_sale_conversion_readiness": {
            "schema_version": "empire.commercial.first_sale_live_conversion_observer.v1",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "status": (
                "NO_CANONICAL_FIRST_PARTY_SALES_ENQUIRIES" if enquiry_count == 0
                else "FIRST_PARTY_ENQUIRY_PRESENT_OWNER_REVIEW_REQUIRED"
            ),
            "canonical_sales_acquisition_counts": {
                "commercial_acquisition_rows": enquiry_count,
                "predictive_acquisition_rows": 0,
                "sales_acquisition_rows": enquiry_count,
                "distinct_sales_prospects": enquiry_count,
                "source_evidence_consistent_rows": enquiry_count,
                "entity_unlinked_acquisition_rows": 0,
                "founder_binding_exact_one_rows": enquiry_count,
                "founder_binding_missing_or_ambiguous_rows": 0,
                "fake_personal_data": "private@example.invalid",
            },
            "canonical_order_or_settlement_evidence_checked": False,
            "verified_first_sale": None,
            "recognized_revenue_cents": None,
            "legacy_buy_ui_manifest_integrity_status": (
                "LEGACY_BUY_UI_HTML_OR_ASSET_INTEGRITY_RELEASE_HOLD" if asset_held
                else "LEGACY_BUY_UI_PINNED_ASSETS_AND_HTML_VERIFIED"
            ),
            "public_conversion_route_status": "PUBLIC_CONVERSION_GET_ROUTES_PRESENT_POST_UNTESTED",
            "outbound_sent": False,
            "payment_action": False,
            "database_writes": False,
        },
    }


def fixture(tmp_path, payload):
    p = tmp_path / "runtime/ops_control/latest.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(payload))
    return tmp_path


def test_three_active_threads_from_authenticated_live_summary(tmp_path):
    root = fixture(tmp_path, original_ops())
    checkpoint = build_checkpoint(root=root, now=NOW)
    assert checkpoint["schema_version"] == SCHEMA
    assert checkpoint["original_ops_state"] == "FRESH_ORIGINAL_OPS_SNAPSHOT"
    assert checkpoint["stream_count"] == 3
    assert [r["lane"] for r in checkpoint["streams"]] == [
        "revenue_buyers", "website_growth", "empireos_core"
    ]
    assert checkpoint["streams"][0]["verified_first_party_sales_enquiries"] == 0
    assert checkpoint["streams"][0]["current_state"] == (
        "ZERO_RECORDED_FIRST_PARTY_SALES_ENQUIRIES"
    )
    assert checkpoint["streams"][1]["current_state"] == (
        "CHECKOUT_RELEASE_HTML_PROVENANCE_HOLD"
    )
    assert checkpoint["streams"][2]["current_state"] == (
        "OPS_RUNNING_WITH_COMMERCIAL_HOLDS"
    )
    assert checkpoint["existing_user_chats_deleted"] is False
    assert checkpoint["payment_or_revenue_recorded"] is False
    assert "private@" not in str(checkpoint)
    assert "must-not-leak" not in str(checkpoint)


def test_one_real_enquiry_is_not_accepted_sale(tmp_path):
    checkpoint = build_checkpoint(root=fixture(tmp_path, original_ops(enquiry_count=1)), now=NOW)
    assert checkpoint["streams"][0]["current_state"] == "FIRST_PARTY_ENQUIRY_OWNER_REVIEW"
    assert checkpoint["streams"][0]["verified_first_party_sales_enquiries"] == 1
    assert checkpoint["streams"][0]["current_revenue_or_settlement_verified_by_this_checkpoint"] is False
    assert checkpoint["payment_or_revenue_recorded"] is False


def test_stale_snapshot_never_reuses_historic_customer_count(tmp_path):
    old = original_ops(enquiry_count=900)
    old["observed_at"] = "2026-09-22T12:00:00+00:00"
    result = build_checkpoint(root=fixture(tmp_path,old),now=NOW)
    assert result["original_ops_state"] == "OPS_SNAPSHOT_STALE"
    assert result["streams"][0]["verified_first_party_sales_enquiries"] is None
    assert result["streams"][0]["current_state"] == "CANONICAL_SALES_EVIDENCE_UNAVAILABLE"
    assert "900" not in str(result)


@pytest.mark.parametrize("change", [
    {"mode": "ACTIVATE"},
    {"healthy": None},
    {"schema_version": "forged"},
    {"observed_at": "2100-01-01T00:00:00+00:00"},
    {"observed_at": "not-a-date"},
])
def test_untrusted_ops_cannot_create_fake_commercial_claims(tmp_path, change):
    result = build_checkpoint(root=fixture(tmp_path,{**original_ops(),**change}),now=NOW)
    assert result["streams"][0]["verified_first_party_sales_enquiries"] is None
    assert result["payment_or_revenue_recorded"] is False


@pytest.mark.parametrize("patch", [
    {"outbound_sent": True},
    {"payment_action": True},
    {"database_writes": True},
    {"execution_authority": "live"},
    {"recognized_revenue_cents": 999999},
    {"verified_first_sale": True},
    {"canonical_order_or_settlement_evidence_checked": True},
    {"canonical_sales_acquisition_counts": {"sales_acquisition_rows": "100"}},
])
def test_privileged_or_malformed_first_sale_source_is_unknown_not_sales(tmp_path,patch):
    raw = original_ops()
    raw["first_sale_conversion_readiness"].update(patch)
    result = build_checkpoint(root=fixture(tmp_path,raw),now=NOW)
    assert result["original_ops_state"] == "FRESH_ORIGINAL_OPS_SNAPSHOT"
    assert result["streams"][0]["verified_first_party_sales_enquiries"] is None
    assert result["streams"][0]["current_state"] == "CANONICAL_SALES_EVIDENCE_UNAVAILABLE"


def test_missing_ops_source_fails_closed(tmp_path):
    result = build_checkpoint(root=tmp_path,now=NOW)
    assert result["original_ops_state"] == "OPS_SOURCE_UNAVAILABLE"
    assert result["streams"][2]["current_state"] == "OPS_SOURCE_STALE_OR_UNAVAILABLE"
    assert all(s.get("next_action") for s in result["streams"])


def test_cli_markdown_and_json_are_readonly(tmp_path, monkeypatch, capsys):
    live = original_ops()
    live["observed_at"] = datetime.now(timezone.utc).isoformat()
    fixture(tmp_path,live)
    monkeypatch.setattr(
        "sys.argv",["review_founder_three_streams_20261020.py",
                    "--read-only","--root",str(tmp_path),"--format","markdown"],
    )
    assert main() == 0
    output = capsys.readouterr().out
    assert "Revenue & Buyers" in output and "Website & Growth" in output
    assert "Three-Chat" in output
    assert "No chats deleted" in output
    monkeypatch.setattr(
        "sys.argv",["review_founder_three_streams_20261020.py",
                    "--read-only","--root",str(tmp_path)],
    )
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["stream_count"] == 3


def test_contradictory_acquisition_counts_not_reported_as_buyer_signal(tmp_path):
    raw = original_ops(enquiry_count=4)
    raw["first_sale_conversion_readiness"]["canonical_sales_acquisition_counts"][
        "founder_binding_exact_one_rows"
    ] = 10
    result = build_checkpoint(root=fixture(tmp_path, raw), now=NOW)
    assert result["streams"][0]["verified_first_party_sales_enquiries"] is None
    assert result["payment_or_revenue_recorded"] is False
