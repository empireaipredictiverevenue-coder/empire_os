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
from empire_os.buyer_thread_discovery import _anchors, DOMAIN, BLOCKED_DOMAINS
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
    additional = {
        row["gmail_thread_id"]:row["entity_key"]
        for row in old.get("threads",[])
        if isinstance(row,dict) and row.get("automatic_discovery_link") is True
    }
    expected={**THREADS, **additional}
    if (not isinstance(rows, list) or len(rows) != len(expected)
            or len(expected)>24):
        raise RelationshipEvidenceError("INCOMPLETE_KNOWN_BUYER_THREAD_SCAN")
    src_rows = old.get("threads")
    if not isinstance(src_rows, list) or len(src_rows)>500:
        raise RelationshipEvidenceError("INVALID_ORIGINAL_RELATIONSHIP_SNAPSHOT")
    if old.get("schema_version") != "empire.buyer_mail_relationship_summary.v1" or old.get("origin") != "connected_gmail_connector_read_only" or old.get("mailbox") != OWN:
        raise RelationshipEvidenceError("INVALID_ORIGINAL_GMAIL_SOURCE")
    known = {}
    for entry in src_rows:
        if isinstance(entry, dict) and entry.get("gmail_thread_id") in expected:
            tid = entry["gmail_thread_id"]
            if tid in known or entry.get("entity_key") != expected[tid]:
                raise RelationshipEvidenceError("DUPLICATE_OR_MISMATCHED_ORIGINAL_THREAD")
            known[tid] = entry
    if set(known) != set(expected):
        raise RelationshipEvidenceError("MISSING_KNOWN_ORIGINAL_BUYER_THREADS")
    updated = deepcopy(old)
    originals = {t["gmail_thread_id"]: t for t in updated["threads"]
                 if isinstance(t, dict) and t.get("gmail_thread_id") in expected}
    found = set()
    totals = 0
    changes = 0
    for thread in rows:
        if not isinstance(thread, dict):
            raise RelationshipEvidenceError("INVALID_THREAD_RECORD")
        tid = thread.get("thread_id")
        if tid not in expected or tid in found or thread.get("truncated") is not False:
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
    if found!=set(expected):
        raise RelationshipEvidenceError("MISSING_EXPECTED_BUYER_THREAD")
    # Discovery is advisory unless an exact anchored two-way prior
    # relationship exists. Unknown company identities are review-only and
    # cannot grant outbound, terms or activation authority.
    discovery=index.get("discovery")
    linked_now=[]
    new_unlinked=[]
    if discovery is not None:
        if (not isinstance(discovery,dict)
                or discovery.get("schema_version")!="empire.buyer_new_thread_discovery.v1"
                or discovery.get("scope")!="RECENT_SENT_TWO_WAY_ONLY"
                or discovery.get("outbound_authorized") is not False
                or discovery.get("execution_authority")!="NONE"):
            raise RelationshipEvidenceError("INVALID_NEW_BUYER_DISCOVERY")
        observed=when(discovery.get("captured_at"))
        if observed is None or abs((observed-polled_at).total_seconds())>300:
            raise RelationshipEvidenceError("INVALID_NEW_BUYER_DISCOVERY_TIME")
        candidates=discovery.get("candidates")
        if not isinstance(candidates,list) or len(candidates)>12:
            raise RelationshipEvidenceError("INVALID_NEW_BUYER_DISCOVERY_COUNT")
        anchored=_anchors(old)
        known_thread_ids={
            r.get("gmail_thread_id") for r in updated["threads"]
            if isinstance(r,dict)
        }
        seen_new=set()
        for item in candidates:
            if not isinstance(item,dict):
                raise RelationshipEvidenceError("INVALID_NEW_BUYER_DISCOVERY_ROW")
            tid=item.get("thread_id")
            domain=item.get("domain")
            if (not isinstance(tid,str) or not HEX.fullmatch(tid)
                    or tid in seen_new
                    or not isinstance(domain,str) or not DOMAIN.fullmatch(domain)
                    or domain in BLOCKED_DOMAINS
                    or item.get("provider_auth_dmarc_aligned") is not True
                    or item.get("outbound_authorized") is not False
                    or item.get("buyer_approved") is not False):
                raise RelationshipEvidenceError("INVALID_NEW_BUYER_DISCOVERY_IDENTITY")
            seen_new.add(tid)
            sent_id=item.get("founder_sent_id")
            reply_id=item.get("buyer_reply_id")
            sent_at=when(item.get("founder_sent_at"))
            reply_at=when(item.get("buyer_reply_at"))
            if (not isinstance(sent_id,str) or not HEX.fullmatch(sent_id)
                    or not isinstance(reply_id,str) or not HEX.fullmatch(reply_id)
                    or sent_id==reply_id or sent_at is None or reply_at is None
                    or (sent_at-clock).total_seconds()>300
                    or (reply_at-clock).total_seconds()>300):
                raise RelationshipEvidenceError("INVALID_NEW_BUYER_DISCOVERY_PROVENANCE")
            recognized=item.get("recognized_events")
            if not isinstance(recognized,list) or len(recognized)>120:
                raise RelationshipEvidenceError("INVALID_NEW_BUYER_DISCOVERY_EVENTS")
            events=[]
            event_keys=set()
            for event in recognized:
                if not isinstance(event,dict) or set(event)!={
                    "message_id","event_code","observed_at","evidence_grade","direction"
                }:
                    raise RelationshipEvidenceError("INVALID_DISCOVERED_EVENT_SHAPE")
                e_mid=event["message_id"]
                e_code=event["event_code"]
                e_when=when(event["observed_at"])
                direction=event["direction"]
                if (not isinstance(e_mid,str) or not HEX.fullmatch(e_mid)
                        or e_code not in EVENT_CODES or e_when is None
                        or (e_when-clock).total_seconds()>300
                        or event["evidence_grade"]!="EMAIL_REPORTED_UNVERIFIED"
                        or direction not in ("inbound","outbound")
                        or (e_code in ("PILOT_TECHNICAL_REQUIREMENTS_SENT",
                                     "COMPLETE_BUYER_REQUIREMENTS_SENT")) != (direction=="outbound")
                        or (e_mid,e_code) in event_keys):
                    raise RelationshipEvidenceError("INVALID_DISCOVERED_EVENT_PROVENANCE")
                event_keys.add((e_mid,e_code))
                events.append(dict(event))
            known_identity=anchored.get(domain)
            if known_identity and item.get("entity_key")==known_identity[0] and item.get("company")==known_identity[1]:
                linked_capacity=sum(
                    x.get("automatic_discovery_link") is True
                    for x in updated["threads"] if isinstance(x,dict)
                )
                if (tid not in known_thread_ids and len(updated["threads"])<500
                        and linked_capacity<20):
                    updated["threads"].append({
                        "gmail_thread_id":tid, "entity_key":known_identity[0],
                        "company":known_identity[1], "identity_domains":[domain],
                        "last_inbound_at":reply_at.isoformat(),
                        "last_inbound_message_id":reply_id,
                        "last_outbound_at":sent_at.isoformat(),
                        "last_outbound_message_id":sent_id,
                        "bounced_addresses":[], "next_action_code":"REVIEW_ONLY",
                        "buyer_signal_events":events,
                        "automatic_discovery_link":True,
                    })
                    linked_now.append(tid)
                    known_thread_ids.add(tid)
                elif tid not in known_thread_ids:
                    new_unlinked.append({
                        "thread_id":tid, "domain":domain,
                        "last_buyer_reply_id":reply_id,
                        "status":"REVIEW_MONITORING_CAP_NO_SEND",
                        "source":"EXACT_TWO_WAY_DMARC_ALIGNED_EMAIL_REPORTED",
                        "outbound_authorized":False,"execution_authority":"NONE",
                    })
            elif item.get("status")=="NEW_DOMAIN_REQUIRES_IDENTITY_REVIEW" and item.get("entity_key") is None and item.get("company") is None:
                paid_only=any(
                    e["event_code"]=="PUBLISHER_SPONSORED_PLACEMENTS_ONLY_REPORTED"
                    and e["direction"]=="inbound" for e in events
                )
                new_unlinked.append({
                    "thread_id":tid, "domain":domain,
                    "last_buyer_reply_id":reply_id,
                    "status":(
                        "HOLD_PAID_PLACEMENTS_ONLY_NO_PERFORMANCE_CONTACT" if paid_only
                        else "REVIEW_IDENTITY_NO_SEND"
                    ),
                    "reported_constraint":(
                        "SPONSORED_PLACEMENTS_ONLY_REPORTED" if paid_only else None
                    ),
                    "source":"EXACT_TWO_WAY_DMARC_ALIGNED_EMAIL_REPORTED",
                    "outbound_authorized":False, "execution_authority":"NONE",
                })
            else:
                raise RelationshipEvidenceError("NEW_DISCOVERY_IDENTITY_CONFLICT")
    # Persist bounded review-only unknown identities; never create a CRM row
    # or treat them as clients until identity is independently checked.
    previous_review=old.get("buyer_new_thread_review",[])
    if not isinstance(previous_review,list) or len(previous_review)>48:
        raise RelationshipEvidenceError("INVALID_PREVIOUS_BUYER_REVIEW")
    review_by_tid={
        row["thread_id"]:row for row in previous_review
        if isinstance(row,dict) and isinstance(row.get("thread_id"),str)
        and HEX.fullmatch(row["thread_id"])
    }
    review_by_tid.update({row["thread_id"]:row for row in new_unlinked})
    updated["buyer_new_thread_review"] = list(review_by_tid.values())[-48:]
    updated["buyer_discovery_status"]={
        "schema_version":"empire.buyer_new_thread_discovery_status.v1",
        "last_scan_at":polled_at.isoformat() if discovery is not None else None,
        "known_threads_linked":len(linked_now),
        "unlinked_identity_review_count":len(updated["buyer_new_thread_review"]),
        "scan_incomplete":(discovery.get("incomplete_scan") if discovery is not None else True),
        "outbound_authorized":False,"execution_authority":"NONE",
    }
    found.update(linked_now)
    # Never falsify the original capture of the other ~53 historical threads.
    updated["partial_update_at"]=polled_at.isoformat()
    updated["partial_updated_thread_ids"]=sorted(found)
    updated["connected_gmail_bridge"]={
        "schema_version":"empire.connected_gmail_metadata_bridge.v1",
        "checked_known_threads":len(found)-len(linked_now),
        "newly_discovered_two_way_links":len(linked_now),
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
        index=_private(ROOT/INDEX,900000)
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
