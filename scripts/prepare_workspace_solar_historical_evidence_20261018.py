#!/usr/bin/env python3
"""Prepare exact six first-party Gmail sent receipts for future DBA review.

Live command defaults to read-only preview; private file-only mode is
explicit. No SQL, CRM, payment, OAuth or outbound code paths are imported.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat

from empire_os.workspace_solar_historical_manifest import (
    HistoricalManifestHeld, read_source_build_manifest, SCHEMA,
)

OUTPUT = Path(
    "/srv/empire_os/runtime/buyer_network_intelligence/"
    "workspace_solar_historical_evidence_20261018.json"
)


def persist_private_manifest(manifest: dict, *, output: Path = OUTPUT) -> str:
    if (not isinstance(manifest, dict)
            or manifest.get("schema_version") != SCHEMA
            or manifest.get("evidence_count") != 6
            or manifest.get("database_writes") is not False
            or manifest.get("outbound_sent") is not False
            or manifest.get("production_schema_activation_authorized") is not False
            or not isinstance(manifest.get("items"), list)
            or len(manifest["items"]) != 6):
        raise HistoricalManifestHeld("INVALID_MANIFEST_FOR_CUSTODY")
    if output.is_symlink():
        raise HistoricalManifestHeld("UNTRUSTED_OUTPUT_SYMLINK")
    if output.exists():
        info = output.stat()
        if (not output.is_file() or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > 25000 or info.st_size == 0):
            raise HistoricalManifestHeld("UNSAFE_EXISTING_EVIDENCE")
        try:
            previous = json.loads(output.read_text("utf-8"))
        except (OSError, ValueError, UnicodeError):
            raise HistoricalManifestHeld("UNREADABLE_EXISTING_EVIDENCE") from None
        if not isinstance(previous,dict):
            raise HistoricalManifestHeld("INVALID_EXISTING_EVIDENCE_OBJECT")
        previous_items=previous.get("items")
        if (not isinstance(previous_items,list) or len(previous_items)!=6
                or any(not isinstance(x,dict) or not all(
                    k in x for k in ("gmail_thread_id","original_provider_message_id","evidence_sha256")
                ) for x in previous_items)):
            raise HistoricalManifestHeld("INVALID_EXISTING_EVIDENCE_ROWS")
        old = {
            (x["gmail_thread_id"],x["original_provider_message_id"],x["evidence_sha256"])
            for x in previous_items
        }
        new = {
            (x["gmail_thread_id"],x["original_provider_message_id"],x["evidence_sha256"])
            for x in manifest["items"]
        }
        if (previous.get("schema_version") != SCHEMA
                or previous.get("evidence_count") != 6
                or len(old) != 6 or old != new
                or sorted(previous.get("items",[]),key=lambda r:r["gmail_thread_id"])
                   != sorted(manifest["items"],key=lambda r:r["gmail_thread_id"])
                or previous.get("outbound_sent") is not False
                or previous.get("database_writes") is not False):
            raise HistoricalManifestHeld("HISTORICAL_EVIDENCE_CONFLICT_NO_OVERWRITE")
        return "EXISTING_IDENTICAL_EVIDENCE_CUSTODY"
    data=(json.dumps(manifest,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")
    if len(data)>25000:
        raise HistoricalManifestHeld("HISTORICAL_EVIDENCE_TOO_LARGE")
    try:
        fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except FileExistsError:
        raise HistoricalManifestHeld("CONCURRENT_EVIDENCE_CUSTODY") from None
    except OSError:
        raise HistoricalManifestHeld("CUSTODY_WRITE_UNAVAILABLE") from None
    return "NEW_PRIVATE_EVIDENCE_CUSTODY_CREATED"


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument("--preview",action="store_true")
    modes.add_argument("--write-private-evidence-only",action="store_true")
    args=parser.parse_args()
    result={
        "mode":"OBSERVE",
        "database_writes":False,
        "crm_records_created":0,
        "outbound_sent":False,
        "schema_migration_executed":False,
    }
    try:
        manifest=read_source_build_manifest()
        if args.write_private_evidence_only:
            result["status"]=persist_private_manifest(manifest)
        else:
            result["status"]="SIX_EVIDENCE_RECEIPTS_PREVIEW_READY"
        result["verified_original_sent_receipts"]=manifest["evidence_count"]
        result["canonical_outbound_intents_created"]=0
        result["source_scanned_at"]=manifest["source_scanned_at"]
    except HistoricalManifestHeld as e:
        result.update(status="HELD_HISTORICAL_SENT_EVIDENCE",reason_code=str(e))
    print(json.dumps(result,sort_keys=True))
    return 0 if result.get("verified_original_sent_receipts")==6 else 2


if __name__=="__main__":
    raise SystemExit(main())
