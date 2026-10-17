"""Buyer-admin review is manual/root-owned and never independently opens routing."""
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.lead_smart_buyer_admin_proof import (
    CAMPAIGN, NUMBER, SCHEMA, verified_buyer_admin_proof,
)

NOW = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)


def valid():
    return {
        "schema_version": SCHEMA,
        "buyer": "Lead Smart",
        "campaign_id": CAMPAIGN,
        "tracking_number": NUMBER,
        "buyer_admin_source_reviewed": True,
        "reviewed_by_founder": True,
        "buyer_admin_source_ref": "gmail:1234567890abcdef",
        "buyer_admin_source_sha256": "a" * 64,
        "buyer_admin_configuration_confirmed": True,
        "reviewed_at_utc": NOW.isoformat(),
        "enabled_direct_buyer_destination_confirmed": True,
        "original_ani_preservation_confirmed": True,
        "recording_mode": "DISABLED",
        "recording_disable_confirmed_by_buyer_admin": True,
    }


def save(root, data):
    path = root / "buyer_admin/verified_configuration.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    return path


def review(root):
    return verified_buyer_admin_proof(
        root, now=NOW, required_owner_uid=os.getuid()
    )


def test_missing_admin_proof_blocks_both(tmp_path):
    assert review(tmp_path) == (False, False)


def test_exact_reviewed_disabled_recording_configuration(tmp_path):
    save(tmp_path, valid())
    assert review(tmp_path) == (True, True)
    # Production never reads user-owned receipts (only root-owned ones).
    if os.getuid() != 0:
        assert verified_buyer_admin_proof(tmp_path, now=NOW) == (False, False)


def test_admin_confirmation_without_disabled_recording_still_blocks_recording(tmp_path):
    data = valid()
    data["recording_mode"] = "ENABLED"
    save(tmp_path, data)
    assert review(tmp_path) == (True, False)


def test_recording_enabled_requires_full_legal_and_admin_controls(tmp_path):
    data = valid()
    data.update({
        "recording_mode": "ENABLED",
        "recording_disable_confirmed_by_buyer_admin": False,
        "caller_notice_and_consent_verified": True,
        "responsible_recording_party_verified": True,
        "recording_access_retention_deletion_verified": True,
        "applicable_call_law_review_complete": True,
        "independent_legal_review_ref": "review:independent-20261013",
    })
    save(tmp_path, data)
    assert review(tmp_path) == (True, True)
    data["applicable_call_law_review_complete"] = "true"
    save(tmp_path, data)
    assert review(tmp_path) == (True, False)


@pytest.mark.parametrize("field,invalid", [
    ("campaign_id", "WRONG"), ("tracking_number", "+18880000000"),
    ("buyer_admin_source_reviewed", "true"), ("reviewed_by_founder", 1),
    ("buyer_admin_configuration_confirmed", "true"),
    ("buyer_admin_source_ref", "not-a-real-ref"),
    ("buyer_admin_source_sha256", "a" * 63),
    ("enabled_direct_buyer_destination_confirmed", "true"),
    ("original_ani_preservation_confirmed", 1),
])
def test_invalid_source_or_type_fails_closed(tmp_path, field, invalid):
    data = valid()
    data[field] = invalid
    save(tmp_path, data)
    result = review(tmp_path)
    assert result != (True, True)
    if field not in {
        "enabled_direct_buyer_destination_confirmed",
        "original_ani_preservation_confirmed",
    }:
        assert result == (False, False)


def test_expired_future_or_timezone_naive_rejected(tmp_path):
    for at in [
        NOW + timedelta(seconds=1),
        NOW - timedelta(days=8),
        NOW.replace(tzinfo=None),
    ]:
        data = valid()
        data["reviewed_at_utc"] = at.isoformat()
        save(tmp_path, data)
        assert review(tmp_path) == (False, False)


def test_symlink_and_weak_permissions_rejected(tmp_path):
    data = valid()
    p = save(tmp_path, data)
    p.chmod(0o666)
    assert review(tmp_path) == (False, False)
    p.chmod(0o600)
    other = tmp_path / "other.json"
    other.write_text(json.dumps(data))
    p.unlink()
    p.symlink_to(other)
    assert review(tmp_path) == (False, False)


def test_missing_admin_evidence_does_not_promote_gateway(tmp_path, monkeypatch):
    from scripts import materialize_lead_smart_launch_readiness as release
    assert release.verified_buyer_admin_proof(tmp_path, now=NOW) == (False, False)


def test_receipt_path_swap_after_open_cannot_substitute_review_data(tmp_path, monkeypatch):
    import empire_os.lead_smart_buyer_admin_proof as proof
    path = save(tmp_path, valid())
    rejected = valid()
    rejected["buyer_admin_configuration_confirmed"] = False
    real_open = proof.os.open

    def swapped_open(requested_path, flags, *args, **kwargs):
        fd = real_open(requested_path, flags, *args, **kwargs)
        # Swap the path after the verified handle has opened. The only
        # allowable read remains the original, validated inode.
        path.unlink()
        replacement = path.with_name("replacement.json")
        replacement.write_text(json.dumps(rejected))
        replacement.chmod(0o600)
        replacement.rename(path)
        return fd

    monkeypatch.setattr(proof.os, "open", swapped_open)
    assert review(tmp_path) == (True, True)
    assert json.loads(path.read_text())["buyer_admin_configuration_confirmed"] is False
