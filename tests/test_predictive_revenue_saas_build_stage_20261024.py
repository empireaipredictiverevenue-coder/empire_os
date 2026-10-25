"""Tests for SaaS demand build inside one existing EmpireOS, no sending."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path

import pytest

from empire_os import predictive_revenue_saas_build_stage as b
from scripts import build_predictive_revenue_saas_demand_stage_20261024 as cli

ROOT = Path("/srv/empire_os")


@pytest.fixture
def source():
    return b._read_source(ROOT / b.SOURCE_REL)


def test_existing_public_source_pack_is_real_build_stage(source):
    report = b.build(ROOT, source, now=date(2026, 10, 24))
    assert report["existing_catalog_product_code"] == "predictive_revenue_diagnostic"
    assert report["existing_os"] == "EmpireOS"
    assert report["existing_database"] == "EmpireDB"
    assert report["existing_crm"] == "Smart CRM"
    assert report["public_signal_count"] == 5
    assert report["external_service_requests_observed"] == 2
    assert report["company_hiring_fit_hypotheses"] == 3
    assert report["private_public_evidence_samples_built"] == 5
    assert report["paid_customer_count_verified"] == 0
    assert report["customer_rows_written"] == 0
    assert report["outbound_send_authorized"] is False
    assert report["new_product_created"] is False
    assert all(x["outbound_ready"] is False for x in report["build_queue"])
    assert all(x["buyer_interest_in_empire_verified"] is False for x in report["build_queue"])


def test_marketplace_request_is_not_named_buyer(source):
    report = b.build(ROOT, source, now=date(2026, 10, 24))
    requests = [x for x in report["build_queue"] if x["external_request_observed"]]
    assert len(requests) == 2
    for row in requests:
        assert row["verified_company_identity"] is False
        assert "ANONYMOUS_BUYER_COMPANY_IDENTITY" in row["gate_blocks"]
        assert "FREELANCER_PLATFORM_ELIGIBILITY_UNVERIFIED" in row["gate_blocks"]
        assert "BUYER_REQUIRED_TECHNICAL_DELIVERY_PROOF_MISSING" in row["gate_blocks"]
        assert row["contact_channel_type"] == "PLATFORM_APPLICATION_ONLY"


@pytest.mark.parametrize("field,value", [
    ("buyer_request_observed", True),
    ("claim_stage", "VERIFIED_CUSTOMER"),
    ("external_procurement_scope", "SALES_PROCESS_BUILD"),
    ("company_identity_verified", False),
    ("route_type", "PLATFORM_APPLICATION_ONLY"),
])
def test_job_ad_cannot_be_promoted_to_buying_request(source, field, value):
    candidate = deepcopy(source)
    row = next(x for x in candidate["records"]
               if x["source_kind"] == "COMPANY_OFFICIAL_HIRING")
    row[field] = value
    with pytest.raises(b.SourceHold):
        b.build(ROOT, candidate, now=date(2026, 10, 24))


@pytest.mark.parametrize("field,value", [
    ("buyer_request_observed", False),
    ("company_identity_verified", True),
    ("claim_stage", "PURCHASE_ORDER"),
    ("route_type", "FOUNDER_PROFESSIONAL_INTRO_REVIEW"),
    ("external_procurement_scope", "NONE"),
])
def test_marketplace_request_cannot_be_certified_into_crm(source, field, value):
    candidate = deepcopy(source)
    row = candidate["records"][0]
    row[field] = value
    with pytest.raises(b.SourceHold):
        b.build(ROOT, candidate, now=date(2026, 10, 24))


@pytest.mark.parametrize("url", [
    "http://www.upwork.com/freelance-jobs",
    "https://www.upwork.com.evil.test/jobs",
    "https://www.upwork.com/",
    "https://www.upwork.com/jobs#send-now",
    "https://user:pass@www.upwork.com/jobs",
    "mailto:vendor@example.com",
])
def test_source_urls_reject_unsafe_or_unreviewed_destinations(source, url):
    candidate = deepcopy(source)
    candidate["records"][0]["source_url"] = url
    with pytest.raises(b.SourceHold):
        b.build(ROOT, candidate, now=date(2026, 10, 24))


def test_duplicate_sources_hold(source):
    candidate = deepcopy(source)
    candidate["records"][1]["source_url"] = candidate["records"][0]["source_url"]
    with pytest.raises(b.SourceHold, match="DUPLICATE"):
        b.build(ROOT, candidate, now=date(2026, 10, 24))


def test_missing_sample_or_symlink_fails_closed(source):
    candidate = deepcopy(source)
    candidate["records"][0]["sample_path"] = (
        "docs/commercial/THIS_DOES_NOT_EXIST_20261024.md"
    )
    with pytest.raises(b.SourceHold, match="SAMPLE"):
        b.build(ROOT, candidate, now=date(2026, 10, 24))


def test_stale_or_future_pack_holds(source):
    with pytest.raises(b.SourceHold, match="STALE"):
        b.build(ROOT, source, now=date(2026, 11, 15))
    with pytest.raises(b.SourceHold, match="STALE"):
        b.build(ROOT, source, now=date(2026, 10, 20))


def test_forged_suppression_status_never_activates_send(source):
    report = b.build(ROOT, source, now=date(2026, 10, 24),
                     suppression_fresh=True)
    assert report["outbound_send_authorized"] is False
    assert all(x["outbound_ready"] is False and
               x["outbound_authorized"] is False for x in report["build_queue"])


def test_writer_is_private_and_only_writes_existing_research_folder(source, tmp_path):
    report = b.build(ROOT, source, now=date(2026, 10, 24))
    target = tmp_path / "saas_demand_build_stage_latest.json"
    b.write_private(target, report)
    assert target.stat().st_mode & 0o077 == 0
    assert json.loads(target.read_text())["customer_rows_written"] == 0
    b.write_private(target, report)
    assert json.loads(target.read_text())["public_signal_count"] == 5


def test_write_private_refuses_symlink_or_exposed_file(source, tmp_path):
    report = b.build(ROOT, source, now=date(2026, 10, 24))
    target = tmp_path / "private.json"
    target.symlink_to(tmp_path / "missing.json")
    with pytest.raises(b.SourceHold):
        b.write_private(target, report)
    target.unlink()
    target.write_text("{}")
    target.chmod(0o644)
    with pytest.raises(b.SourceHold):
        b.write_private(target, report)


def test_cli_is_readonly_by_default(capsys):
    assert cli.main(["--repo-root", str(ROOT)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["private_read_model_written"] is False
    assert report["status"] == "SAAS_DEMAND_PRIVATE_BUILD_STAGE_PASS"
    assert report["emails_sent"] == 0


# Canonical source/next-action safeguards added after initial private build.
from datetime import datetime, timezone


def _gtm_snapshot(status="CANONICAL_COMMERCIAL_SALES_INTAKE_ZERO_OBSERVED",
                  verified=True, count=0, timestamp="2026-10-24T22:22:35+00:00"):
    return {"schema_version": "empire.gtm.integration_observer.v1",
            "generated_at": timestamp,
            "canonical_sales_source_ops": {
                "status": status, "source_count_verified": verified,
                "canonical_sales_acquisitions": count,
                "canonical_commercial_enquiries": count,
                "canonical_predictive_revenue_enquiries": count}}


def _queue_snapshot(fresh=False, timestamp="2026-10-24T22:23:00+00:00"):
    return {"schema_version": "buyer-network-candidate-queue-v1",
            "generated_at": timestamp, "gmail_snapshot_fresh": fresh}


def test_canonical_hold_is_unknown_not_fake_zero():
    s = b.commercial_truth(
        _gtm_snapshot(status="HELD_CANONICAL_ACQUISITION_OWNER_OPS_RECEIPT_REQUIRED",
                      verified=False, count=None), _queue_snapshot(),
        now=datetime(2026, 10, 24, 22, 25, tzinfo=timezone.utc))
    assert s["status"] == "CANONICAL_SOURCE_UNKNOWN"
    assert s["canonical_sales_acquisitions_if_verified"] is None
    assert s["source_to_tenant_crm_lineage_verified"] is False
    assert s["accepted_sale_verified"] is False


def test_exact_recent_verified_zero_never_means_paid_or_named_buyer():
    s = b.commercial_truth(
        _gtm_snapshot(), _queue_snapshot(),
        now=datetime(2026, 10, 24, 22, 25, tzinfo=timezone.utc))
    assert s["status"] == "RECENT_CANONICAL_SOURCE_ZERO_OBSERVED"
    assert s["canonical_sales_acquisitions_if_verified"] == 0
    assert s["named_real_buyer_identity_verified"] is False
    assert s["payments_verified"] is False
    assert s["outbound_authority"] is False


@pytest.mark.parametrize("kwargs", [
    {"count": 2}, {"verified": False},
    {"timestamp": "2026-10-20T22:22:35+00:00"},
    {"timestamp": "tomorrow"},
    {"timestamp": "2026-10-24T23:22:35+00:00"},
])
def test_untrusted_partial_or_stale_canonical_status_holds(kwargs):
    s = b.commercial_truth(
        _gtm_snapshot(**kwargs), _queue_snapshot(),
        now=datetime(2026, 10, 24, 22, 25, tzinfo=timezone.utc))
    assert s["status"] == "CANONICAL_SOURCE_UNKNOWN"
    assert s["canonical_sales_acquisitions_if_verified"] is None


def test_untrusted_gmail_freshness_cannot_grant_outbound_authority(source):
    snap = _queue_snapshot(fresh=True)
    now = datetime(2026, 10, 24, 22, 25, tzinfo=timezone.utc)
    obs = b.commercial_truth(_gtm_snapshot(), snap, now=now)
    assert obs["original_buyer_network_gmail_snapshot_fresh"] is True
    assert obs["outbound_authority"] is False
    stale = _queue_snapshot(fresh=True, timestamp="2026-10-22T22:23:00+00:00")
    assert b.commercial_truth(_gtm_snapshot(), stale, now=now)[
        "original_buyer_network_gmail_snapshot_fresh"] is False
    result = b.build(ROOT, source, now=date(2026, 10, 24),
                     intake_observer=_gtm_snapshot(), buyer_queue=snap)
    assert result["outbound_send_authorized"] is False
    assert not any(a["ready_for_email"] for a in result["next_review_actions"])


def test_action_order_prioritizes_low_spend_founder_review_not_expected_revenue(source):
    r = b.build(ROOT, source, now=date(2026, 10, 24))
    actions = r["next_review_actions"]
    assert [a["review_rank"] for a in actions] == sorted(
        a["review_rank"] for a in actions)
    assert actions[0]["source_id"] == "clueso_founding_ae_20261024"
    assert actions[0]["action"] == "VERIFY_FOUNDER_NETWORK_CHANNEL_AND_CANONICAL_SUPPRESSION"
    assert actions[0]["ready_for_email"] is False
    assert r["review_order_is_not_expected_revenue"] is True
    assert r["marketplace_submission_authorized"] is False
    assert all(a["owner"] == "EXISTING_COMMERCIAL_ACQUISITION_OWNER" for a in actions)


def test_snapshot_reader_rejects_symlink_and_malformed(tmp_path):
    from scripts.build_predictive_revenue_saas_demand_stage_20261024 import (
        _existing_readonly_snapshot,
    )
    (tmp_path / "owner.json").write_text('{"schema_version":"example"}')
    assert _existing_readonly_snapshot(tmp_path, "owner.json") == {
        "schema_version": "example"}
    (tmp_path / "other.json").symlink_to(tmp_path / "owner.json")
    assert _existing_readonly_snapshot(tmp_path, "other.json") is None
    (tmp_path / "bad.json").write_text("{not-json")
    assert _existing_readonly_snapshot(tmp_path, "bad.json") is None


def test_clueso_official_verified_is_never_contact_permission():
    def official_get(url):
        if url.endswith("/careers/founding-ae"):
            return url, 200, b"Neel Balar / PLG signups / Oct 13, 2026"
        return url, 200, b"Partnerships and referrals / Privacy and data requests"
    p = b.verify_clueso_official_sources(get=official_get)
    assert p["status"] == "OFFICIAL_CLUESO_PAGES_GET_VERIFIED"
    assert all(row["verified"] for row in p["source_checks"])
    assert p["independent_external_procurement_verified"] is False
    assert p["linkedin_outreach_authorized"] is False
    assert p["email_outreach_authorized"] is False
    assert p["customer_records_written"] is False


@pytest.mark.parametrize("tamper", [
    "redirect", "missing_slogan", "oversize", "wrong_status",
])
def test_clueso_official_fails_closed_for_uncertain_source(tamper):
    def official_get(url):
        text = (b"Neel Balar / PLG signups / Oct 13, 2026" if "founding-ae" in url
                else b"Partnerships and referrals / Privacy and data requests")
        if tamper == "redirect":
            return "https://evil.example/careers", 200, text
        if tamper == "missing_slogan":
            return url, 200, b"Founding Account Executive"
        if tamper == "oversize":
            return url, 200, b"x" * 250_001
        return url, 503, text
    p = b.verify_clueso_official_sources(get=official_get)
    assert p["status"] == "OFFICIAL_CLUESO_PAGES_HELD"
    assert p["email_outreach_authorized"] is False
    assert p["linkedin_outreach_authorized"] is False


def test_clueso_official_partial_source_never_promotes_buyer():
    def official_get(url):
        if url.endswith("/contact"):
            raise OSError("network unavailable")
        return url, 200, b"Neel Balar / PLG signups / Oct 13, 2026"
    p = b.verify_clueso_official_sources(get=official_get)
    assert p["status"] == "OFFICIAL_CLUESO_PAGES_HELD"
    assert any(not row["verified"] for row in p["source_checks"])
    assert p["independent_external_procurement_verified"] is False


def test_founder_reported_clueso_send_no_repeat_and_no_false_delivery(source):
    receipt = b.load_founder_clueso_first_touch(ROOT / b.FOUNDER_CLUESO_REPORT_REL)
    assert receipt["founder_reported_sent"] is True
    report = b.build(ROOT, source, now=date(2026, 10, 25))
    updated = b.apply_founder_clueso_first_touch(
        report, receipt, now=date(2026, 10, 25))
    assert updated["founder_reported_linkedin_manual_first_touch_count"] == 1
    assert updated["real_buyer_conversations_verified"] == 0
    assert updated["new_emails_sent"] == 0
    assert updated["customer_rows_written"] == 0
    assert updated["outbound_send_authorized"] is False
    assert updated["founder_reported_first_touch"]["platform_send_or_delivery_verified"] is False
    row = next(x for x in updated["build_queue"]
               if x["source_id"] == "clueso_founding_ae_20261024")
    assert row["first_touch_no_repeat"] is True
    assert row["reply_verified"] is False
    assert row["buyer_interest_in_empire_verified"] is False
    action = next(x for x in updated["next_review_actions"]
                  if x["source_id"] == "clueso_founding_ae_20261024")
    assert action["action"] == "AWAIT_AUTHENTIC_LINKEDIN_REPLY_NO_DUPLICATE_INTRO"
    assert action["ready_for_email"] is False
    assert action["approved_followup"] is False
    assert updated["next_review_actions"][0]["source_id"] != "clueso_founding_ae_20261024"


@pytest.mark.parametrize("key,value", [
    ("provider_delivered_verified", True),
    ("positive_reply_verified", True),
    ("crm_promotion_authorized", True),
    ("authorizes_followup", True),
    ("prospect_source_id", "other_prospect"),
    ("channel", "EMAIL"),
])
def test_founder_confirmation_cannot_be_spoofed_into_commercial_authority(
    source, key, value
):
    receipt = b.load_founder_clueso_first_touch(ROOT / b.FOUNDER_CLUESO_REPORT_REL)
    edited = dict(receipt, **{key: value})
    with pytest.raises(b.SourceHold):
        b.apply_founder_clueso_first_touch(
            b.build(ROOT, source, now=date(2026, 10, 25)),
            edited, now=date(2026, 10, 25))


def test_historical_self_report_no_repeat_never_expires(source):
    receipt = b.load_founder_clueso_first_touch(ROOT / b.FOUNDER_CLUESO_REPORT_REL)
    report = b.build(ROOT, source, now=date(2026, 10, 25))
    updated = b.apply_founder_clueso_first_touch(
        report, receipt, now=date(2027, 10, 25))
    assert updated["founder_reported_first_touch"]["first_touch_no_repeat"] is True


def test_report_loader_rejects_symlink(tmp_path):
    receipt = tmp_path / "founder.json"
    receipt.write_text("{}")
    link = tmp_path / "alias.json"
    link.symlink_to(receipt)
    with pytest.raises(b.SourceHold):
        b.load_founder_clueso_first_touch(link)


def test_four_person_saas_public_sample_replaces_generic_hubspot_diagnostic(source):
    report = b.build(ROOT, source, now=date(2026, 10, 25))
    rows = {row["source_id"]: row for row in report["build_queue"]}
    assert rows["revops_saas_salesprocess_20261024"]["sample_path"] == (
        "docs/commercial/FOUR_PERSON_SAAS_SALES_PROCESS_PUBLIC_SAMPLE_20261025.md")
    assert rows["revops_hubspot_20261024"]["sample_path"] == (
        "docs/commercial/REVOPS_BUYER_REQUEST_FREE_EVIDENCE_SAMPLE_20261024.md")
    assert rows["revops_saas_salesprocess_20261024"]["sample_sha256"]
    assert report["private_public_evidence_samples_built"] == 5
    actions = {r["source_id"]:r for r in report["next_review_actions"]}
    assert actions["revops_saas_salesprocess_20261024"]["review_rank"] == 2
    assert actions["revops_hubspot_20261024"]["review_rank"] == 3
    assert "FOUR_PERSON" in actions["revops_saas_salesprocess_20261024"][
        "review_priority_basis"]
    assert actions["revops_saas_salesprocess_20261024"]["ready_for_application"] is False
    assert report["outbound_send_authorized"] is False


def test_original_no_repeat_survives_four_person_priority_update(source):
    receipt = b.load_founder_clueso_first_touch(ROOT / b.FOUNDER_CLUESO_REPORT_REL)
    report = b.apply_founder_clueso_first_touch(
        b.build(ROOT, source, now=date(2026, 10, 25)), receipt,
        now=date(2026, 10, 25))
    assert report["next_review_actions"][0]["source_id"] == (
        "revops_saas_salesprocess_20261024")
    clueso = next(x for x in report["next_review_actions"]
                  if x["source_id"]=="clueso_founding_ae_20261024")
    assert clueso["first_touch_no_repeat"] is True
    assert clueso["approved_followup"] is False
    assert report["founder_reported_first_touch"]["platform_send_or_delivery_verified"] is False


def test_marketplace_public_sample_does_not_enable_send_when_suppression_passed(source):
    report = b.build(ROOT, source, now=date(2026, 10, 25),
                     suppression_fresh=True)
    for r in report["next_review_actions"]:
        assert r["ready_for_email"] is False
        assert r["ready_for_application"] is False
    assert report["marketplace_submission_authorized"] is False
