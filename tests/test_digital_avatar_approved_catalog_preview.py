"""Founder's exact approved V1 price candidate; preview-only existing EmpireDB RPCs."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from empire_os.digital_avatar_approved_catalog_preview import (
    APPROVAL_REF, APPROVAL_SOURCE, ENTERPRISE_RECURRING_FLOOR_CENTS, SCHEMA,
    CatalogStagingHold, build_approved_avatar_catalog_preview,
)

NOW = datetime(2026, 10, 11, 21, 50, tzinfo=timezone.utc)
PRODUCT_CODES = (
    "digital_avatar_copilot",
    "digital_avatar_workforce",
    "digital_avatar_white_label_workforce",
)


def catalog(*, now=NOW, items=()):
    products = [{"product_code": code} for code in items]
    return {
        "schema_version": "empire.commercial-product-catalog.v1",
        "generated_at": now.isoformat(),
        "product_count": len(products),
        "products": products,
        "execution_authority": "none",
        "actual_revenue": False,
    }


def propose(snapshot=None):
    return build_approved_avatar_catalog_preview(
        snapshot or catalog(), now=NOW,
    )


def test_exact_founder_approved_policy_without_economics_activation():
    packet = propose()
    assert packet["schema_version"] == SCHEMA
    assert packet["status"] == "FOUNDER_PRICE_APPROVED_CATALOG_PREVIEW_READY"
    assert packet["approval_reference"] == APPROVAL_REF
    assert packet["approval_source"] == APPROVAL_SOURCE
    assert packet["mode"] == "DRY_RUN"
    assert packet["candidate_count"] == 3
    assert packet["enterprise_recurring_floor_cents"] == 1_500_000
    assert packet["enterprise_floor_is_quote_led_only"] is True
    assert packet["target_margin_bps_is_policy_not_verified_actual"] == 7500
    assert packet["minimum_margin_bps_is_policy_not_verified_actual"] == 7000
    assert packet["costs_verified"] is False
    assert packet["capacity_verified"] is False
    assert packet["meeting_duration_verified"] is False
    assert packet["database_mutation"] is False
    assert packet["catalog_versions_proposed"] is False
    assert packet["catalog_product_identity_created"] is False
    assert packet["binding_terms_ready"] is False
    assert packet["checkout_authorized"] is False
    assert packet["payment_authority"] == "none"
    assert packet["outbound_authorized"] is False
    assert packet["actual_revenue"] is False
    assert packet["execution_authority"] == "none"


def test_prices_usage_and_versions_exactly_match_founders_prior_decision():
    packet = propose()
    rows = packet["products"]
    assert [x["product_code"] for x in rows] == list(PRODUCT_CODES)
    expected = [
        (150000, 150000, 1, 40, 1, 3500),
        (500000, 500000, 5, 150, 3, 3000),
        (1250000, 1500000, 15, 400, 10, 2500),
    ]
    for row, amounts in zip(rows, expected):
        assert tuple(row[key] for key in (
            "monthly_price_cents", "implementation_fee_cents",
            "included_active_avatars",
            "included_verified_meetings_per_month",
            "proposed_concurrency_entitlement",
            "overage_per_verified_meeting_cents",
        )) == amounts
        assert row["founder_approved_price_basis"]["state"] == "VERIFIED"
        assert row["founder_approved_price_basis"]["approval_reference"] == APPROVAL_REF
        assert row["proposed_policy_margin_bps"] == 7500
        assert row["observed_actual_margin_verified"] is False
        assert row["catalog_state"] == "NOT_PROPOSED"
        assert row["version_state"] == "NOT_PROPOSED"
        assert row["binding_terms_ready"] is False
        assert row["sellable"] is False
        assert row["checkout_authorized"] is False


def test_existing_empiredb_rpc_payload_keys_are_exactly_bounded():
    for row in propose()["products"]:
        reg = row["canonical_product_identity_rpc_preview"]
        ver = row["canonical_product_version_rpc_preview"]
        assert reg["method"] == ver["method"] == "POST"
        assert reg["invoked"] is False
        assert ver["invoked"] is False
        assert reg["path"] == "/rest/v1/rpc/register_commercial_product_identity"
        assert ver["path"] == "/rest/v1/rpc/propose_commercial_product_version"
        assert set(reg["payload"]) == {
            "p_product_code", "p_product_name", "p_product_family",
            "p_billing_model", "p_configuration", "p_provenance", "p_actor",
        }
        assert set(ver["payload"]) == {
            "p_product_code", "p_billing_model", "p_currency",
            "p_price_basis", "p_acquisition_cost_basis",
            "p_fulfilment_cost_basis", "p_margin_policy",
            "p_provenance", "p_evidence_refs",
            "p_effective_from", "p_effective_until", "p_actor",
        }
        assert reg["payload"]["p_product_code"] == row["product_code"]
        assert reg["payload"]["p_product_family"] == "digital_avatar"
        assert ver["payload"]["p_price_basis"]["state"] == "VERIFIED"
        assert ver["payload"]["p_price_basis"]["source_type"] == "founder_approved"
        assert ver["payload"]["p_price_basis"]["approval_reference"] == APPROVAL_REF
        assert ver["payload"]["p_acquisition_cost_basis"]["state"] == "UNKNOWN"
        assert ver["payload"]["p_fulfilment_cost_basis"]["state"] == "UNKNOWN"
        assert ver["payload"]["p_margin_policy"]["state"] == "UNKNOWN"
        assert ver["payload"]["p_provenance"]["binding_terms_ready"] is False
        assert ver["payload"]["p_effective_from"] is None
        assert ver["payload"]["p_effective_until"] is None
        assert APPROVAL_REF in ver["payload"]["p_evidence_refs"]
        assert reg["payload"]["p_configuration"]["entitlements_verified"] is False
        assert reg["payload"]["p_configuration"]["runtime_capacity_verified"] is False
        assert reg["payload"]["p_configuration"]["binding_terms_ready"] is False


def test_preview_never_modifies_catalog_snapshot():
    snapshot = catalog(items=("existing_mrr_seat",))
    before = deepcopy(snapshot)
    out = propose(snapshot)
    assert snapshot == before
    assert out["catalog_product_count_before"] == 1


@pytest.mark.parametrize("code", PRODUCT_CODES)
def test_existing_avatar_product_identity_holds_instead_of_duplicates(code):
    with pytest.raises(CatalogStagingHold, match="existing_avatar_catalog_identity"):
        propose(catalog(items=(code,)))


@pytest.mark.parametrize("data", [
    {"approval_reference":"founder_approval:2026-10-02:someone_else"},
    {"approval_reference":""},
])
def test_untrusted_approval_ref_never_promotes_price(data):
    with pytest.raises(CatalogStagingHold, match="exact_existing_founder"):
        build_approved_avatar_catalog_preview(catalog(), now=NOW, **data)


@pytest.mark.parametrize(("key","value","expected"), [
    ("schema_version","random-schema","authority_or_schema"),
    ("execution_authority","db_write","authority_or_schema"),
    ("actual_revenue",True,"authority_or_schema"),
    ("generated_at","2026-10-09T20:00:00+00:00","stale_or_future"),
    ("generated_at","2030-01-01T00:00:00+00:00","stale_or_future"),
    ("generated_at","2026-10-11T21:50:00","naive"),
    ("product_count",True,"count_mismatch"),
    ("product_count",5,"count_mismatch"),
    ("products","wrong type","unbounded"),
])
def test_schema_authority_freshness_and_count_fail_closed(key,value,expected):
    packet = catalog()
    packet[key] = value
    with pytest.raises(CatalogStagingHold, match=expected):
        propose(packet)


def test_duplicate_existing_catalog_codes_fail_closed():
    with pytest.raises(CatalogStagingHold,match="duplicate_products"):
        propose(catalog(items=("same_code","same_code")))


def test_malformed_existing_row_and_oversized_catalog_fail_closed():
    a=catalog()
    a["products"]=[{"product_name":"No code"}]
    a["product_count"]=1
    with pytest.raises(CatalogStagingHold,match="identity_invalid"):
        propose(a)
    b=catalog(items=[f"p{i}" for i in range(501)])
    with pytest.raises(CatalogStagingHold,match="unbounded"):
        propose(b)


def test_no_db_connectors_called_when_generating_preview(monkeypatch):
    import empire_os.digital_avatar_approved_catalog_preview as module
    import empire_os.sb as db
    monkeypatch.setattr(db,"request_json",lambda *a,**k:
                        pytest.fail("DB RPC EXECUTED IN PREVIEW"))
    out=module.build_approved_avatar_catalog_preview(catalog(),now=NOW)
    assert all(x["canonical_product_version_rpc_preview"]["invoked"] is False
               for x in out["products"])


def test_cli_has_no_apply_flag(monkeypatch,capsys,tmp_path):
    from scripts.preview_approved_digital_avatar_catalog import main
    p=tmp_path/"runtime/commercial_catalog/latest.json"
    p.parent.mkdir(parents=True)
    live=catalog(now=datetime.now(timezone.utc))
    p.write_text(json.dumps(live))
    original=p.read_bytes()
    monkeypatch.setattr("sys.argv",["preview","--repo-root",str(tmp_path)])
    assert main()==0
    report=json.loads(capsys.readouterr().out)
    assert report["database_mutation"] is False
    assert p.read_bytes()==original
    monkeypatch.setattr("sys.argv",["preview","--apply","--repo-root",str(tmp_path)])
    with pytest.raises(SystemExit):
        main()


def test_cli_rejects_catalog_overwrite_and_replay_with_changed_content(monkeypatch,capsys,tmp_path):
    from scripts.preview_approved_digital_avatar_catalog import main
    p=tmp_path/"runtime/commercial_catalog/latest.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(catalog(now=datetime.now(timezone.utc))))
    previous=p.read_bytes()
    monkeypatch.setattr("sys.argv",["preview","--repo-root",str(tmp_path),"--output",str(p)])
    assert main()==2
    assert p.read_bytes()==previous
    report=json.loads(capsys.readouterr().out)
    assert report["status"]=="HELD"
    dest=tmp_path/"runtime/commercial_proposals/digital_avatar_approved_price_v1.json"
    monkeypatch.setattr("sys.argv",["preview","--repo-root",str(tmp_path),"--output",str(dest)])
    assert main()==0
    assert dest.exists()
    before=dest.read_bytes()
    # Same args and time produces another timestamp => deliberate safe replay hold.
    assert main()==2
    assert dest.read_bytes()==before



def _write_price_record(root, packet):
    target = (root / "runtime/commercial_proposals"
              / "digital_avatar_approved_price_v1.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(packet))
    return target


def test_recorded_approval_is_exact_price_policy_not_live_catalog(tmp_path):
    from empire_os.digital_avatar_approved_catalog_preview import (
        has_recorded_price_only_founder_approval,
    )
    assert has_recorded_price_only_founder_approval(tmp_path) is False
    _write_price_record(tmp_path,propose())
    assert has_recorded_price_only_founder_approval(tmp_path) is True


@pytest.mark.parametrize(("field","value"), [
    ("approval_reference", "founder_approval:2026-10-03:unknown"),
    ("approval_scope", "LIVE_EXECUTE"),
    ("database_mutation", True),
    ("catalog_versions_proposed", True),
    ("binding_terms_ready", True),
    ("checkout_authorized", True),
    ("payment_authority", "bsc_send"),
    ("actual_revenue", True),
    ("candidate_count", True),
])
def test_tampered_approval_record_never_reclassifies_gate(tmp_path,field,value):
    from empire_os.digital_avatar_approved_catalog_preview import (
        has_recorded_price_only_founder_approval,
    )
    packet=propose()
    packet[field]=value
    _write_price_record(tmp_path,packet)
    assert has_recorded_price_only_founder_approval(tmp_path) is False


def test_tampered_price_basis_or_rpc_invocation_never_reclassifies(tmp_path):
    from empire_os.digital_avatar_approved_catalog_preview import (
        has_recorded_price_only_founder_approval,
    )
    for mutate in [
        lambda p: p["products"][0].update({"monthly_price_cents":100}),
        lambda p: p["products"][0].update({"included_active_avatars":True}),
        lambda p: p["products"][0]["founder_approved_price_basis"].update({"amount_cents":100}),
        lambda p: p["products"][0]["canonical_product_version_rpc_preview"].update({"invoked":True}),
        lambda p: p["products"][0]["canonical_product_version_rpc_preview"]["payload"]["p_acquisition_cost_basis"].update({"state":"VERIFIED"}),
        lambda p: p["products"][0].update({"version_state":"VERIFIED"}),
    ]:
        p=propose()
        mutate(p)
        _write_price_record(tmp_path,p)
        assert has_recorded_price_only_founder_approval(tmp_path) is False


def _create_approval_reconciliation_fixture(tmp_path):
    from hashlib import sha256
    from empire_os.digital_avatar_approved_catalog_preview import (
        AVATAR_PRICING_CHECKLIST_ITEM,
        AVATAR_PRICING_CHECKLIST_SECTION,
    )
    from empire_os.master_execution_ledger import parse_checklist
    other="FOUNDER APPROVAL REQUIRED: a completely unrelated operation"
    content=(
        "# Master\n## " + AVATAR_PRICING_CHECKLIST_SECTION + "\n"
        + "- [ ] " + AVATAR_PRICING_CHECKLIST_ITEM + "\n"
        + "## Other Department\n- [ ] " + other + "\n"
    )
    checklist=tmp_path/"docs/MASTER_REMAINING_CHECKLIST.md"
    checklist.parent.mkdir(parents=True, exist_ok=True)
    checklist.write_text(content)
    rows=parse_checklist(checklist)
    packets=[]
    for row in rows:
        cid="check_"+sha256(
            f"{row.line}|{row.section}|{row.item}".encode()
        ).hexdigest()[:16]
        packets.append({
            "item_ids":[cid],"checklist_lines":[row.line],
            "department":"strategy_executive",
            "execution_class":"founder_gate",
            "verification_contract_ready":False,
        })
    source=tmp_path/"runtime/execution_plane/business_completion_dispatch_latest.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps({
        "canonical_total_count":2,"canonical_done_count":0,
        "source_pending_count":2,"packets":packets
    }))
    return checklist,rows


def test_task_monitor_no_longer_reasks_approved_pricing_while_closure_held(tmp_path):
    from empire_os.completion_reconciliation import refresh_completion_reconciliation
    from empire_os.completion_task_monitor import build_completion_task_monitor
    from empire_os.master_execution_ledger import parse_checklist
    source,rows=_create_approval_reconciliation_fixture(tmp_path)
    current=refresh_completion_reconciliation(tmp_path,now=NOW)
    assert current["status"]=="AVAILABLE"
    assert current["state_counts"]=={"FOUNDER_GATE":2}
    assert current["digital_avatar_price_policy_approval_recorded"] is False
    assert current["verified_done_count"]==0
    assert source.read_text().count("- [ ]")==2
    _write_price_record(tmp_path,propose())
    updated=refresh_completion_reconciliation(tmp_path,now=NOW)
    assert updated["status"]=="AVAILABLE"
    assert updated["digital_avatar_price_policy_approval_recorded"] is True
    assert updated["state_counts"]=={
        "FOUNDER_PRICE_POLICY_APPROVED_FORMAL_CLOSURE_PENDING":1,
        "FOUNDER_GATE":1,
    }
    assert updated["verified_done_count"]==0
    assert updated["automatic_checklist_mutation_allowed"] is False
    assert updated["production_mutation"] is False
    assert source.read_text().count("- [ ]")==2
    monitor=build_completion_task_monitor(
        parse_checklist(source),updated,now=NOW,
    )
    assert monitor["tracked_pending_count"]==2
    assert monitor["state_counts"]=={
        "FOUNDER_PRICE_POLICY_APPROVED_FORMAL_CLOSURE_PENDING":1,
        "FOUNDER_GATE":1,
    }
    approved=next(x for x in monitor["items"] if
                  x["state"]=="FOUNDER_PRICE_POLICY_APPROVED_FORMAL_CLOSURE_PENDING")
    assert "Do not request pricing approval again" in approved["next_evidence_step"]
    assert approved["commercial_outcome_verified"] is False
    assert monitor["checklist"]["pending"]==2
    assert monitor["execution_authority"]=="none"


def test_invalid_snapshot_keeps_exact_price_approval_gate_held(tmp_path):
    from empire_os.completion_reconciliation import refresh_completion_reconciliation
    _create_approval_reconciliation_fixture(tmp_path)
    p=propose()
    p["products"][0]["canonical_product_version_rpc_preview"]["payload"]["p_margin_policy"]["state"]="VERIFIED"
    _write_price_record(tmp_path,p)
    updated=refresh_completion_reconciliation(tmp_path,now=NOW)
    assert updated["status"]=="AVAILABLE"
    assert updated["digital_avatar_price_policy_approval_recorded"] is False
    assert updated["state_counts"]=={"FOUNDER_GATE":2}
    assert updated["verified_done_count"]==0
