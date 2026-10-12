#!/usr/bin/env python3
"""Import verified Gmail connector *metadata*, never bodies, to buyer registry.

The ChatGPT Gmail connector supplies a complete previously known thread index.
This process does NOT connect to Gmail, ask for OAuth credentials, contact a
recipient, or admit canonical commercial authority. No account discovery.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parseaddr
import json
from pathlib import Path
import re

from empire_os.commercial_relationship_registry import RelationshipEvidenceError, when
from empire_os.buyer_mail_semantics import EVENT_CODES
from scripts.reconcile_buyer_email_relationships import atomic_private_write

ROOT = Path("/srv/empire_os")
REL = Path("runtime/buyer_network_intelligence")
INDEX = REL / "buyer_partner_message_index_20261010.json"
SOURCE = REL / "gmail_relationship_evidence_latest.json"
SCHEMA = "empire.buyer_gmail_original_message_index.v1"
OWN = "flavag83@gmail.com"
THREADS = {
    "1a0d9ce883c87d4a": "lead-smart",
    "1a0cfb65e0dd960e": "leadbank",
    "1a0cfb667dca0957": "validated",
    "1a0d9fa5b944630a": "connexis",
}
HEX = re.compile(r"^[0-9a-f]{16,32}$")
EMAIL = re.compile(r"^[a-z0-9._+%-]+@[a-z0-9.-]+\.[a-z]{2,24}$")


def _private(path: Path, max_size: int) -> dict:
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size > max_size
            or path.stat().st_mode & 0o077):
        raise RelationshipEvidenceError("UNSAFE_PRIVATE_GMAIL_EVIDENCE")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RelationshipEvidenceError("INVALID_GMAIL_INPUT")
    return data


# Connected Gmail sometimes returns sender metadata as "Display Name user@host"
# without RFC-822 angle brackets. Extract exactly one syntactically valid
# address, and keep the existing known-buyer-domain + thread binding checks.
SENDER_ADDR = re.compile(
    r"(?<![a-zA-Z0-9._+%\-@])"
    r"([a-zA-Z0-9._+%\-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,24})"
    r"(?![a-zA-Z0-9._+%\-@])"
)


def _addr(value: object) -> str:
    if not isinstance(value, str) or len(value) > 512 or any(
        c in value for c in ("\r", "\n", "\x00")
    ):
        return ""
    addresses = SENDER_ADDR.findall(value)
    if len(addresses) != 1:
        return ""
    single = addresses[0].lower()
    return single if EMAIL.fullmatch(single) else ""


def _provider_email_timestamp(value: object):
    # The connected Gmail adapter emits email_ts as a UTC wall-clock string
    # without a timezone, unlike the EmpireOS ISO 8601 canonical records.
    # This mapping has been cross-checked against previously stored provider
    # message ids/timestamps; do not apply it to arbitrary user input.
    if isinstance(value,str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}",value):
        value=value+"+00:00"
    return when(value)


def refreshed_summary(
    old: dict, index: dict, *, now: datetime | None = None,
) -> tuple[dict, dict]:
    clock = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if index.get("schema_version") != SCHEMA:
        raise RelationshipEvidenceError("INVALID_GMAIL_INDEX_SCHEMA")
    if index.get("source") not in ("connected_gmail_connector_read_only", "empire_gmail_api_readonly"):
        raise RelationshipEvidenceError("GMAIL_CONNECTOR_PROVENANCE_REQUIRED")
    polled_at = when(index.get("collected_at"))
    if polled_at is None or not 0 <= (clock-polled_at).total_seconds() <= 600:
        raise RelationshipEvidenceError("GMAIL_CONNECTOR_POLL_NOT_CURRENT")
    rows = index.get("threads")
    if not isinstance(rows, list) or len(rows) != len(THREADS):
        raise RelationshipEvidenceError("INCOMPLETE_KNOWN_BUYER_THREAD_SCAN")
    src_rows = old.get("threads")
    if not isinstance(src_rows, list) or len(src_rows)>500:
        raise RelationshipEvidenceError("INVALID_ORIGINAL_RELATIONSHIP_SNAPSHOT")
    if old.get("schema_version") != "empire.buyer_mail_relationship_summary.v1" or old.get("origin") != "connected_gmail_connector_read_only" or old.get("mailbox") != OWN:
        raise RelationshipEvidenceError("INVALID_ORIGINAL_GMAIL_SOURCE")
    known = {}
    for entry in src_rows:
        if isinstance(entry, dict) and entry.get("gmail_thread_id") in THREADS:
            tid = entry["gmail_thread_id"]
            if tid in known or entry.get("entity_key") != THREADS[tid]:
                raise RelationshipEvidenceError("DUPLICATE_OR_MISMATCHED_ORIGINAL_THREAD")
            known[tid] = entry
    if set(known) != set(THREADS):
        raise RelationshipEvidenceError("MISSING_KNOWN_ORIGINAL_BUYER_THREADS")
    updated = deepcopy(old)
    originals = {t["gmail_thread_id"]: t for t in updated["threads"]
                 if isinstance(t, dict) and t.get("gmail_thread_id") in THREADS}
    found = set()
    totals = 0
    changes = 0
    for thread in rows:
        if not isinstance(thread, dict):
            raise RelationshipEvidenceError("INVALID_THREAD_RECORD")
        tid = thread.get("thread_id")
        if tid not in THREADS or tid in found or thread.get("truncated") is not False:
            raise RelationshipEvidenceError("UNTRUSTED_OR_PARTIAL_THREAD")
        if thread.get("partner") != known[tid]["company"]:
            raise RelationshipEvidenceError("PARTNER_THREAD_LABEL_MISMATCH")
        found.add(tid)
        msgs = thread.get("messages")
        if not isinstance(msgs, list) or not 1 <= len(msgs) <= 80 or thread.get("message_count") != len(msgs):
            raise RelationshipEvidenceError("THREAD_MESSAGE_COUNT_INCOMPLETE")
        totals += len(msgs)
        domains = set(known[tid]["identity_domains"])
        latest = {"inbound":(None,None),"outbound":(None,None)}
        ids = set()
        recognized = []
        for m in msgs:
            if not isinstance(m,dict) or not HEX.fullmatch(str(m.get("id") or "")) or m["id"] in ids:
                raise RelationshipEvidenceError("INVALID_OR_DUPLICATE_GMAIL_MESSAGE_ID")
            ids.add(m["id"])
            if any(field in m for field in ("body", "snippet", "raw_mime", "raw_mime_base64url", "password", "oauth_token")):
                raise RelationshipEvidenceError("RAW_MAIL_OR_CREDENTIAL_IN_METADATA_BRIDGE")
            ts = _provider_email_timestamp(m.get("date"))
            if ts is None or (ts-clock).total_seconds()>300:
                raise RelationshipEvidenceError("INVALID_GMAIL_MESSAGE_TIME")
            labels=m.get("labels")
            if not isinstance(labels,list) or len(labels)>25 or any(not isinstance(label,str) or len(label)>85 for label in labels):
                raise RelationshipEvidenceError("INVALID_GMAIL_MESSAGE_LABELS")
            labelset=set(labels)
            if "TRASH" in labelset or "DRAFT" in labelset:
                continue
            sender=_addr(m.get("from"))
            if sender==OWN and "SENT" in labelset:
                direction="outbound"
            elif (sender and sender.split("@",1)[1] in domains
                    and "SENT" not in labelset and "SPAM" not in labelset):
                direction="inbound"
            else:
                continue
            event_codes = m.get("recognized_codes", [])
            if (not isinstance(event_codes, list) or len(event_codes)>len(EVENT_CODES)
                    or len(event_codes)!=len(set(event_codes))
                    or any(not isinstance(code,str) or code not in EVENT_CODES
                           for code in event_codes)):
                raise RelationshipEvidenceError("INVALID_BUYER_RECOGNITION_EVENT")
            for code in event_codes:
                if (code in ("PILOT_TECHNICAL_REQUIREMENTS_SENT",
                             "COMPLETE_BUYER_REQUIREMENTS_SENT")) != (direction=="outbound"):
                    raise RelationshipEvidenceError("RECOGNITION_EVENT_DIRECTION_MISMATCH")
                recognized.append({
                    "message_id":m["id"], "event_code":code,
                    "observed_at":ts.isoformat(),
                    "evidence_grade":"EMAIL_REPORTED_UNVERIFIED",
                    "direction":direction,
                })
            if latest[direction][0] is None or ts>latest[direction][0]:
                latest[direction]=(ts,m["id"])
        target=originals[tid]
        # Replace only this reviewed thread's bounded recognised claim codes.
        # Claimed calls/ANI/recording are NEVER provider-side verification.
        target["buyer_signal_events"] = recognized[:120]
        for direction,(ts,msg_id) in latest.items():
            if ts is None:
                continue
            old_ts=when(target.get("last_"+direction+"_at"))
            if old_ts is not None and ts<old_ts:
                raise RelationshipEvidenceError("REFRESH_WOULD_REWIND_KNOWN_BUYER_HISTORY")
            if old_ts is None or ts>old_ts:
                changes+=1
                target["last_"+direction+"_at"]=ts.isoformat()
                target["last_"+direction+"_message_id"]=msg_id
            elif target.get("last_"+direction+"_message_id")!=msg_id:
                raise RelationshipEvidenceError("CONFLICTING_GMAIL_MESSAGE_AT_SAME_TIME")
    if found!=set(THREADS):
        raise RelationshipEvidenceError("MISSING_EXPECTED_BUYER_THREAD")
    # Never falsify the original capture of the other ~53 historical threads.
    updated["partial_update_at"]=polled_at.isoformat()
    updated["partial_updated_thread_ids"]=sorted(found)
    updated["connected_gmail_bridge"]={
        "schema_version":"empire.connected_gmail_metadata_bridge.v1",
        "checked_known_threads":len(found),
        "checked_message_count":totals,
        "collected_at":polled_at.isoformat(),
        "read_only":True,
        "server_gmail_oauth_configured":False,
        "original_unchanged_thread_capture":old["captured_at"],
        "outbound_authorized":False,
        "execution_authority":"NONE",
    }
    return updated,{"known_threads_checked":len(found),"messages_checked":totals,
                    "new_history_directions":changes,"gmail_oauth_on_server":False,
                    "outbound_authorized":False}


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--write",action="store_true")
    args=ap.parse_args()
    try:
        base=ROOT/REL
        index=_private(ROOT/INDEX,400000)
        source=_private(ROOT/SOURCE,2500000)
        updated, summary=refreshed_summary(source,index)
        if args.write:
            atomic_private_write(ROOT/SOURCE, updated)
    except (OSError,ValueError,TypeError,json.JSONDecodeError) as exc:
        print(json.dumps({"status":"BLOCKED","reason_code":str(exc) if isinstance(exc, RelationshipEvidenceError) else type(exc).__name__,
                          "outbound_authorized":False}))
        return 2
    print(json.dumps({"status":"PASS","written":args.write,**summary},
                     sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
