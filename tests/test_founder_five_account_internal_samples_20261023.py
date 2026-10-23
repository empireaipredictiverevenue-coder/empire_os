"""Internal pilot samples stay original-source-only and fail closed."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

import pytest

from empire_os.founder_acquisition_us_market import INPUT, load_us_inputs
from empire_os.workspace_solar_reply_tracking import EvidenceHeld
from scripts.review_founder_five_account_internal_samples_20261023 import (
    prepare_internal_samples, write_private_sample, PRIVATE_SAMPLE,
    SOURCE_EVIDENCE, STATUS_READY,
)

NOW = datetime(2026, 10, 23, 21, 45, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parent.parent


def make_inputs(tmp_path: Path):
    source = tmp_path / INPUT
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes((ROOT / INPUT).read_bytes())
    rows = load_us_inputs(tmp_path)
    unique = {}
    for row in rows:
        unique[row["source_url"]] = row["source_role"]
    assert len(rows) == 20 and len(unique) == 17

    out = tmp_path / SOURCE_EVIDENCE
    out.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(out.parent, 0o700)
    record = {
        "schema_version": "empire.founder_acquisition_us_evidence.v1",
        "status": "US_PUBLIC_EVENT_EVIDENCE_REVIEW_ONLY",
        "market": "US",
        "actual_buyers_verified": 0,
        "revenue_verified": False,
        "outbound_sent": False,
        "crm_writes": False,
        "automatic_send_authorized": False,
        "execution_authority": "none",
        "approved_price": False,
        "sources": [
            {
                "source_url": url,
                "source_role": role,
                "observed_at_utc": (NOW - timedelta(minutes=10)).isoformat(),
                "source_sha256": "a" * 64,
                "source_status": "PUBLISHED_EVENT_CLAIM_OBSERVED_NOT_BUYER_VERIFIED",
                "actual_customer_demand": False,
                "outbound_authorized": False,
            }
            for url,role in unique.items()
        ],
    }
    out.write_text(json.dumps(record),encoding="utf-8")
    out.chmod(0o600)
    return out, record


def test_four_source_based_samples_are_not_buyers_or_price_commitments(tmp_path):
    make_inputs(tmp_path)
    data = prepare_internal_samples(tmp_path, now=NOW)
    assert data["status"] == STATUS_READY
    assert data["source_verified_hypotheses"] == 20
    assert set(data["groups"]) == {"Alloovium","Libra Robotics","Andco","Plena Health"}
    assert all(len(group) == 5 for group in data["groups"].values())
    assert all(len({x["account"] for x in group}) == 5 for group in data["groups"].values())
    for group in data["groups"].values():
        for account in group:
            assert account["buyer_intent"] == "NOT_VERIFIED"
            assert account["procurement_contact"] == "NOT_VERIFIED"
            assert account["buyer_permission_to_contact"] == "NOT_VERIFIED"
            assert account["original_publisher_url"].startswith("https://")
            assert account["key_disqualification_risk"]
    assert data["verified_buyers"] == 0
    assert data["authentic_buyer_response_verified"] is False
    assert data["pilot_quote_approved"] is False
    assert data["pilot_customer_accepted"] is False
    assert data["pilot_payment_verified"] is False
    assert data["outbound_governor_activate"] is False
    assert data["auto_followups"] is False
    assert data["outbound_sent"] is False
    assert data["crm_writes"] is False


def test_sample_writes_only_existing_private_runtime_snapshot(tmp_path):
    make_inputs(tmp_path)
    report = prepare_internal_samples(tmp_path, now=NOW)
    path = write_private_sample(tmp_path, report)
    assert path == tmp_path / PRIVATE_SAMPLE
    assert path.stat().st_mode & 0o077 == 0
    assert path.parent.stat().st_mode & 0o077 == 0
    assert json.loads(path.read_text())["groups"] == report["groups"]
    assert write_private_sample(tmp_path, report) == path


@pytest.mark.parametrize("change", [
    "stale", "future", "removed", "unverified", "conflicting_url",
    "approved", "outbound", "buyer", "bad_hash", "source_mismatch",
])
def test_missing_or_wrong_publisher_proof_blocks_entire_pack(tmp_path,change):
    out,record=make_inputs(tmp_path)
    if change == "stale":
        record["sources"][0]["observed_at_utc"] = (NOW - timedelta(days=8)).isoformat()
    elif change == "future":
        record["sources"][0]["observed_at_utc"] = (NOW + timedelta(hours=2)).isoformat()
    elif change == "removed":
        record["sources"].pop()
    elif change == "unverified":
        record["sources"][0]["source_status"] = "HELD_SOURCE_NOT_CORROBORATED"
    elif change == "conflicting_url":
        record["sources"][1]["source_url"] = record["sources"][0]["source_url"]
    elif change == "approved":
        record["approved_price"] = True
    elif change == "outbound":
        record["outbound_sent"] = True
    elif change == "buyer":
        record["actual_buyers_verified"] = 1
    elif change == "bad_hash":
        record["sources"][0]["source_sha256"] = "not-validated"
    elif change == "source_mismatch":
        record["sources"][0]["source_role"] = "COMPANY_DISTRIBUTED_WIRE"
    out.write_text(json.dumps(record),encoding="utf-8")
    with pytest.raises(EvidenceHeld):
        prepare_internal_samples(tmp_path,now=NOW)


def test_private_source_mode_and_symlink_protection(tmp_path):
    out,record=make_inputs(tmp_path)
    out.chmod(0o644)
    with pytest.raises(EvidenceHeld,match="SOURCE_SNAPSHOT_UNSAFE"):
        prepare_internal_samples(tmp_path,now=NOW)
    out.chmod(0o600)
    report=prepare_internal_samples(tmp_path,now=NOW)
    output=tmp_path / PRIVATE_SAMPLE
    target=tmp_path / "outside"
    target.write_text("not-to-overwrite")
    output.symlink_to(target)
    with pytest.raises(EvidenceHeld,match="PRIVATE_OUTPUT_LOCATION_UNSAFE"):
        write_private_sample(tmp_path,report)
    assert target.read_text()=="not-to-overwrite"


def test_unaware_clock_is_not_accepted(tmp_path):
    make_inputs(tmp_path)
    with pytest.raises(EvidenceHeld,match="AWARE_CLOCK_REQUIRED"):
        prepare_internal_samples(tmp_path,now=datetime(2026,10,23,21,45))
