"""Field-level licensing preflight: no synthetic approval can authorise export."""
from copy import deepcopy
from datetime import datetime, timedelta
import pytest

from empire_os.data_exchange_rights_preflight import (
    build_rights_preflight, PLANNING_FIELDS, PROCUREMENT_FIELDS,
    REVIEWER_CHECKS,
)
from test_data_exchange_agi_bridge import NOW, source, procurement as fixture_proc


def report(*, proc=None, snapshots=None, at=NOW):
    return build_rights_preflight(
        source_snapshots=source() if snapshots is None else snapshots,
        procurement=proc, assessed_at=at,
    )


def test_planning_only_fields_have_real_source_vs_derived_provenance():
    r = report()
    assert r["source_record_count"] == 1
    assert r["procurement_notice_count"] == 0
    assert r["source_licence_class"] == "OPEN_GOVERNMENT_LICENCE_V3_STATED"
    assert r["commercial_reuse_permitted_in_principle"] is True
    assert r["independent_field_rights_review"] == "NOT_COMPLETED"
    assert len(r["field_lineage"]) == len(PLANNING_FIELDS)
    by_name = {x["field_name"]: x for x in r["field_lineage"]}
    assert by_name["source_record_id"]["field_provenance"] == "government_published_field"
    assert by_name["source_observed_at"]["field_provenance"] == "empire_observation"
    assert by_name["observed_history_change"]["field_provenance"] == "empire_derived_evaluation"
    assert not any(x["customer_distribution_grant"] for x in r["field_lineage"])
    assert not any(x["status"] != "PENDING_REVIEW" for x in r["reviewer_checklist"])
    assert len(r["reviewer_checklist"]) == len(REVIEWER_CHECKS)
    assert r["customer_delivery_enabled"] is False
    assert r["data_resale_authorized"] is False
    assert r["outbound_enabled"] is False
    assert r["execution_authority"] == "NONE"


def test_two_sources_are_attributed_separately_and_never_joined():
    r = report(proc=fixture_proc())
    assert r["procurement_notice_count"] == 1
    assert len(r["rights_evidence"]) == 2
    assert len(r["field_lineage"]) == len(PLANNING_FIELDS) + len(PROCUREMENT_FIELDS)
    assert "© Crown copyright and database right 2026" in (
        x["statement"] for x in r["rights_evidence"]
    )
    assert all(x["licence_uri"].endswith("/version/3/") for x in r["rights_evidence"])
    assert r["source_causation_verified"] is False
    assert r["saleable_product_verified"] is False
    assert r["paid_buyer_validated"] is False
    assert "email" in r["excluded_by_design"]
    assert "contactPoint" in r["excluded_by_design"]


def test_repeatable_evidence_digest_scopes_exact_source_records_and_rights():
    base = report(proc=fixture_proc())
    replay = report(proc=fixture_proc())
    assert base == replay
    modified = source(changed=True)
    changed = report(proc=fixture_proc(), snapshots=modified)
    assert base["source_evidence_sha256"] != changed["source_evidence_sha256"]


@pytest.mark.parametrize("tamper", [
    lambda s: s[1].update({"rights_review_eligible": True}),
    lambda s: s[1]["records"][0].update({"email": "alice@example.com"}),
    lambda s: s[1].update({"customer_delivery_enabled": True}),
    lambda s: s[1]["records"][0].update({"source_url": "https://evil.invalid"}),
])
def test_forged_planning_approval_or_private_data_fail_closed(tamper):
    snaps = source()
    tamper(snaps)
    with pytest.raises(ValueError):
        report(snapshots=snaps)


@pytest.mark.parametrize("tamper", [
    lambda p: p.update({"cross_source_entity_link": "VERIFIED"}),
    lambda p: p.update({"data_resale_authorized": True}),
    lambda p: p["notices"][0].update({"email": "alice@example.com"}),
])
def test_forged_procurement_clearing_and_private_data_fail_closed(tamper):
    payload = deepcopy(fixture_proc())
    tamper(payload)
    with pytest.raises(ValueError):
        report(proc=payload)


def test_stale_or_untrusted_approval_cannot_generate_rights_receipt():
    with pytest.raises(ValueError):
        report(at=NOW + timedelta(days=100))
    with pytest.raises(ValueError):
        report(at=datetime(2026, 10, 14))


def test_preflight_is_finite_no_records_or_contact_list_leaks():
    r = report(proc=fixture_proc())
    text = repr(r)
    assert "private@example.org" not in text
    assert "PRIVATE-TENDER-DESCRIPTION" not in text
    assert "1739547" not in text
    assert "096757-2026" not in text


def test_read_only_rights_operator_returns_provenance_without_source_records(
    tmp_path, capsys,
):
    import json
    from scripts.review_data_exchange_source_rights import main

    obs = source()
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(obs[0]), encoding="utf-8")
    b.write_text(json.dumps(obs[1]), encoding="utf-8")
    c = tmp_path / "procurement.json"
    c.write_text(json.dumps(fixture_proc()), encoding="utf-8")
    original = sorted(p.name for p in tmp_path.iterdir())

    assert main([
        "--snapshots", str(a), str(b), "--procurement", str(c),
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["source_record_count"] == 1
    assert result["procurement_notice_count"] == 1
    assert result["customer_delivery_enabled"] is False
    assert result["commercial_reuse_permitted_in_principle"] is True
    assert result["independent_field_rights_review"] == "NOT_COMPLETED"
    assert sorted(p.name for p in tmp_path.iterdir()) == original


def test_rights_operator_invalid_file_yields_redacted_hold(tmp_path, capsys):
    import json
    from scripts.review_data_exchange_source_rights import main

    bad = tmp_path / "confidential.json"
    bad.write_text('{"secret":"NEVER_DISCLOSE_THIS"}', encoding="utf-8")
    assert main([
        "--snapshots", str(bad), str(bad),
    ]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "HOLD"
    assert result["execution_authority"] == "NONE"
    assert "NEVER_DISCLOSE_THIS" not in str(result)
