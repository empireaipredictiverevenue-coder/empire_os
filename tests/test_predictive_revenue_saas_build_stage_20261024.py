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
    assert report["private_public_evidence_samples_built"] == 4
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
