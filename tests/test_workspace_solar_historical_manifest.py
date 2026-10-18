"""Only real-bound Gmail send evidence, never retrospective CRM approval."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os

import pytest

from tests.test_workspace_solar_founder_review import NOW, snapshot
from empire_os.workspace_solar_historical_manifest import (
    HistoricalManifestHeld, build_historical_manifest, SCHEMA,
)
from scripts.prepare_workspace_solar_historical_evidence_20261018 import (
    persist_private_manifest,
)


def manifest():
    return build_historical_manifest(snapshot(),now=NOW)


def test_six_immutable_original_provider_receipts_have_no_claim_of_crm_authority():
    data=manifest()
    assert data["schema_version"]==SCHEMA
    assert data["evidence_count"]==6
    assert len({x["gmail_thread_id"] for x in data["items"]})==6
    assert len({x["evidence_sha256"] for x in data["items"]})==6
    assert all(len(x["recipient_sha256"])==64 for x in data["items"])
    assert all(len(x["evidence_sha256"])==64 for x in data["items"])
    assert all(x["historical_approval_attested"] is False for x in data["items"])
    assert all(x["canonical_outbound_intent_admitted"] is False for x in data["items"])
    assert all(x["crm_contact_bound"] is False for x in data["items"])
    assert data["canonical_outbound_intents_created"]==0
    assert data["database_writes"] is False
    assert data["outbound_sent"] is False
    assert data["production_schema_activation_authorized"] is False
    assert "info@gbnrg" not in json.dumps(data)
    assert "PRIVATE MESSAGE CONTENT" not in json.dumps(data)


@pytest.mark.parametrize("bad",[
    lambda data: data["threads"].pop(),
    lambda data: data["threads"][0].update(sent_message_id="abc"),
    lambda data: data["threads"][0].update(sent_verified_in_authenticated_mailbox=False),
    lambda data: data["threads"][0].update(sent_at="not-time"),
    lambda data: data.update(founder_crm_ingest_verified=True),
    lambda data: data.update(gmail_message_bodies_retained=True),
    lambda data: data.update(scanned_at="2026-10-17T10:00:00+00:00"),
])
def test_invalid_untrusted_metadata_cannot_create_an_evidence_manifest(bad):
    inp=snapshot()
    bad(inp)
    with pytest.raises(HistoricalManifestHeld):
        build_historical_manifest(inp,now=NOW)


def test_private_evidence_file_is_idempotent_and_0600(tmp_path):
    output=tmp_path/"manifest.json"
    data=manifest()
    assert persist_private_manifest(data,output=output)=="NEW_PRIVATE_EVIDENCE_CUSTODY_CREATED"
    assert (output.stat().st_mode & 0o777)==0o600
    before=output.read_bytes()
    assert persist_private_manifest(data,output=output)=="EXISTING_IDENTICAL_EVIDENCE_CUSTODY"
    assert output.read_bytes()==before


def test_different_provider_original_message_cannot_replace_historical_evidence(tmp_path):
    output=tmp_path/"manifest.json"
    data=manifest()
    persist_private_manifest(data,output=output)
    changed=deepcopy(data)
    changed["items"][0]["evidence_sha256"]="f"*64
    with pytest.raises(HistoricalManifestHeld,match="HISTORICAL_EVIDENCE_CONFLICT_NO_OVERWRITE"):
        persist_private_manifest(changed,output=output)


def test_symlink_attack_and_bad_permissions_fail_closed(tmp_path):
    output=tmp_path/"manifest.json"
    target=tmp_path/"private"
    target.write_text("not real")
    output.symlink_to(target)
    with pytest.raises(HistoricalManifestHeld,match="UNTRUSTED_OUTPUT_SYMLINK"):
        persist_private_manifest(manifest(),output=output)
    output.unlink()
    output.write_text(json.dumps(manifest()))
    os.chmod(output,0o644)
    with pytest.raises(HistoricalManifestHeld,match="UNSAFE_EXISTING_EVIDENCE"):
        persist_private_manifest(manifest(),output=output)
