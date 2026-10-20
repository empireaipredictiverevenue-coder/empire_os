"""Outbox diff and owner-trust intake tests. No production keys or buyers."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import json
import os

import pytest

from empire_os.a2a_owner_pickup_change_tracking_v1 import review_pickup_changes
from empire_os.a2a_owner_receipt_intake_v1 import (
    load_candidate_receipts, inspect_owner_receipt_files,
    trusted_owner_keys,
)
from tests.test_a2a_owner_research_protocol_v1_20261020 import pickup, keys, sign


def test_unchanged_owner_research_does_not_generate_new_task_proposal():
    first = pickup()
    initial = review_pickup_changes(first)
    assert initial["new_request_count"] == 4
    assert initial["unchanged_request_count"] == 0
    repeated = review_pickup_changes(first, deepcopy(first))
    assert repeated["new_request_count"] == 0
    assert repeated["unchanged_request_count"] == 4
    assert repeated["discovery_cycle_did_not_dispatch"]


def test_new_or_revised_request_reported_without_lead_promotion():
    old = pickup()
    new = deepcopy(old)
    row = new["pickup_by_owner"]["buyer_scout"][0]
    row["ticket_sha256"] = "f"*64
    track = review_pickup_changes(new, old)
    assert track["changed_request_count"] == 1
    assert track["new_request_count"] == 0
    assert track["buyer_leads_created"] == 0
    assert track["owner_acks_created"] == 0


def test_rejects_invalid_outbox_permissions_and_counts():
    old = pickup()
    bad = deepcopy(old)
    bad["owner_dispatches"] = 1
    with pytest.raises(ValueError, match="UNTRUSTED"):
        review_pickup_changes(bad, old)
    bad = deepcopy(old)
    bad["pickup_count"] += 1
    with pytest.raises(ValueError, match="INVALID_OWNER_PICKUP_COUNT"):
        review_pickup_changes(bad, old)


def test_untrusted_local_file_does_not_register_owner_signature(tmp_path: Path):
    p = pickup()
    pair, _ = keys()
    row = p["pickup_by_owner"]["buyer_scout"][0]
    receipt = sign(row, pair["buyer_scout"])
    folder = tmp_path / "owner_receipts"
    folder.mkdir()
    (folder / f'{receipt["owner"]}_{receipt["ticket_id"]}.json').write_text(
        json.dumps(receipt))
    # A user-writable file cannot be a trusted owner public-key allowlist.
    local = tmp_path / "self_certified_keys.json"
    local.write_text(json.dumps({
        "schema_version": "empire.a2a.trusted_owner_keys.v1",
        "trusted_owners": {},
    }))
    if os.geteuid() != 0:
        with pytest.raises(ValueError, match="PERMISSIONS"):
            trusted_owner_keys(local)
    r = inspect_owner_receipt_files(p, folder, trusted_config=tmp_path / "nonexistent.json")
    assert r["authenticated_owner_replies"] == 0
    assert r["trust_store_state"] == "NO_PRODUCTION_OWNER_PUBLIC_KEYS_CONFIGURED"
    assert r["received_receipt_file_count"] == 1
    assert "TRUSTED_OWNER_PUBLIC_KEY_NOT_CONFIGURED" in r["rejection_reason_codes"]


def test_filename_mismatch_and_symlink_are_rejected(tmp_path: Path):
    p = pickup()
    folder = tmp_path / "receipts"
    folder.mkdir()
    (folder / "not_a_real_owner.json").write_text('{"owner":"buyer_scout"}')
    with pytest.raises(ValueError, match="UNSAFE_OWNER_RECEIPT_ENTRY"):
        load_candidate_receipts(folder)
    state = inspect_owner_receipt_files(p, folder, trusted_config=tmp_path/"no_keys")
    assert state["receipt_input_state"] == "OWNER_RECEIPT_DIRECTORY_REJECTED"
    assert state["authenticated_owner_replies"] == 0
    (folder / "not_a_real_owner.json").unlink()
    shortcut = tmp_path / "shortcut"
    shortcut.symlink_to(folder)
    with pytest.raises(ValueError, match="UNSAFE_OWNER_RECEIPT_DIRECTORY"):
        load_candidate_receipts(shortcut)
