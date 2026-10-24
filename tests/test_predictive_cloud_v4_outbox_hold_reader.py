"""Original Predictive Cloud V4.3 read-only outbox replay/authority hold."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from empire_os.predictive_cloud_v4_outbox_hold_reader import (
    V4ProjectionHold, review_held_outbox,
)

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts/rehearse_predictive_cloud_v4_held_outbox_20261024.sh"
TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"


def row(*, revision=13, latest=15, withdrawn=True, kind="OBSERVED"):
    return {
        "event_digest": "c" * 64,
        "tenant_id": TENANT,
        "sector": "roofing",
        "entity_digest": "a" * 64,
        "source_evidence_digest": "b" * 64,
        "revision": revision,
        "event_kind": kind,
        "delivery_state": "HELD",
        "execution_authority": "none",
        "latest_revision": latest,
        "withdrawn": withdrawn,
        "source_review_state": "UNVERIFIED",
        "watermark_source_digest": "b" * 64,
    }


def test_held_reader_never_promotes_observations_or_replay():
    result = review_held_outbox([row()], requested_tenant_id=TENANT)
    assert result["reviewed_count"] == 1
    assert result["redis_publish_authorized"] is False
    assert result["execution_authority"] == "none"
    assert result["source_authority_verified"] is False
    assert result["crm_tenant_membership_verified"] is False
    assert result["reviews"][0]["reason"] == "WITHDRAWN_SOURCE_HELD"
    assert result["reviews"][0]["redis_publish_authorized"] is False


def test_held_reader_separates_superseded_from_unverified_latest():
    old = row(revision=13, latest=14, withdrawn=False)
    new = row(revision=14, latest=14, withdrawn=False)
    new["event_digest"] = "d" * 64
    result = review_held_outbox([old, new], requested_tenant_id=TENANT)
    assert [r["reason"] for r in result["reviews"]] == [
        "SUPERSEDED_REVISION_HELD",
        "UNVERIFIED_TENANT_AND_SOURCE_HELD",
    ]
    assert not any(r["redis_publish_authorized"] for r in result["reviews"])


@pytest.mark.parametrize("field,value,reason", [
    ("tenant_id", OTHER, "cross_tenant_row_refused"),
    ("event_digest", "untrusted@email.test", "invalid_event_digest"),
    ("entity_digest", "a" * 63, "invalid_entity_digest"),
    ("source_evidence_digest", "b" * 63, "invalid_source_evidence_digest"),
    ("watermark_source_digest", "0" * 64, "latest_source_digest_mismatch"),
    ("delivery_state", "SENT", "unexpected_release_or_source_authority"),
    ("execution_authority", "dispatch", "unexpected_release_or_source_authority"),
    ("source_review_state", "VERIFIED", "unexpected_release_or_source_authority"),
    ("withdrawn", "false", "unexpected_release_or_source_authority"),
    ("latest_revision", 12, "revision_regression_or_invalid"),
    ("revision", 0, "revision_regression_or_invalid"),
    ("event_kind", "TRANSFER", "unexpected_release_or_source_authority"),
])
def test_held_reader_rejects_injected_rows(field, value, reason):
    event = row(revision=13, latest=13, withdrawn=False)
    event[field] = value
    with pytest.raises(V4ProjectionHold, match=reason):
        review_held_outbox([event], requested_tenant_id=TENANT)


def test_held_reader_refuses_incomplete_and_duplicate_rows():
    missing = row()
    missing.pop("delivery_state")
    with pytest.raises(V4ProjectionHold, match="row_schema_inexact"):
        review_held_outbox([missing], requested_tenant_id=TENANT)
    with pytest.raises(V4ProjectionHold, match="duplicate_event_digest_in_snapshot"):
        review_held_outbox([row(), row()], requested_tenant_id=TENANT)
    with pytest.raises(V4ProjectionHold, match="reader_rows_unbounded"):
        review_held_outbox([row()] * 33, requested_tenant_id=TENANT)


def test_held_reader_withdrawal_requires_current_tombstone():
    record = row(revision=13, latest=14, withdrawn=True, kind="WITHDRAWN")
    with pytest.raises(V4ProjectionHold, match="withdrawal_tombstone_inconsistent"):
        review_held_outbox([record], requested_tenant_id=TENANT)


def test_empty_snapshot_is_not_evidence_of_source_verification():
    result = review_held_outbox([], requested_tenant_id=TENANT)
    assert result["status"] == "NO_HELD_EVENTS"
    assert result["source_authority_verified"] is False
    assert result["redis_publish_authorized"] is False


def test_held_reader_has_no_driver_connector_or_production_worker():
    source = (ROOT / "empire_os/predictive_cloud_v4_outbox_hold_reader.py").read_text()
    for forbidden in ("psycopg.connect", "redis.Redis(", "create_engine(",
                      "subprocess.run(", "smtplib.", "websocket_connect("):
        assert forbidden not in source
    assert "predictive_cloud_v4_outbox_hold_reader" not in (
        ROOT / "empire_os/hub.py"
    ).read_text()


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,
                    reason="isolated PG cluster unavailable")
def test_live_temporary_postgres_produces_authority_held_reader_snapshot():
    process = subprocess.run(["pg_virtualenv", "-t", "bash", str(HARNESS)],
                             cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert process.returncode == 0, process.stdout[-4000:] + process.stderr[-4000:]
    assert "V4_064_HELD_READER_SNAPSHOT=PASS" in process.stdout
    assert "V4_064_DISPOSABLE_ONLY" in process.stdout
    assert "Dropping cluster 18/regress" in process.stdout + process.stderr
