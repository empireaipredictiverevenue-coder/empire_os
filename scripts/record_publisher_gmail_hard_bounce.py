#!/usr/bin/env python3
"""Record exactly one Gmail-confirmed hard bounce in canonical EmpireDB.

Defaults to a no-DB-read dry run. A founder-approved production insert
requires --apply --approved-gettradesmen-bounce and EMPIREDB_DSN.
No prospect, intent, reply, sending, or revenue records are mutated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path("/srv/empire_os")
PROOF = ROOT / "docs/commercial/PUBLISHER_RECRUITMENT_GMAIL_SEND_EVIDENCE_20261010.json"
RECIPIENT = "gettradesmen@gmail.com"
SENT_MESSAGE_ID = "1a126bc1e0be02d6"
BOUNCE_MESSAGE_ID = "1a126bc2866c04ea"
REASON = "hard_bounce_550_5_1_1"
SOURCE = "gmail_dsn:" + BOUNCE_MESSAGE_ID


class EvidenceHold(ValueError):
    pass


def verify_proof(path: Path = PROOF) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 50000:
        raise EvidenceHold("PROOF_FILE_UNSAFE")
    raw = path.read_bytes()
    proof = json.loads(raw)
    if (
        not isinstance(proof, dict)
        or proof.get("schema_version") != "empire.publisher_recruitment.gmail_sent_evidence.v1"
        or proof.get("source_mailbox") != "flavag83@gmail.com"
        or proof.get("submitted_to_gmail_count") != 4
        or proof.get("confirmed_hard_bounce_count") != 1
        or proof.get("empire_os_outbound_governor_send") is not False
    ):
        raise EvidenceHold("UNTRUSTED_SEND_SUMMARY")
    messages = proof.get("messages")
    if not isinstance(messages, list) or len(messages) != 4:
        raise EvidenceHold("INVALID_SEND_ROWS")
    if len({m.get("recipient") for m in messages if isinstance(m, dict)}) != 4:
        raise EvidenceHold("DUPLICATED_SEND_RECIPIENTS")
    hard = [m for m in messages if m.get("recipient_delivery_status") is not None]
    if len(hard) != 1 or hard[0] != next(
        (m for m in messages if m.get("recipient") == RECIPIENT), None
    ):
        raise EvidenceHold("UNEXPECTED_BOUNCE_RECIPIENT")
    row = hard[0]
    if (
        row.get("gmail_message_id") != SENT_MESSAGE_ID
        or row.get("bounce_gmail_message_id") != BOUNCE_MESSAGE_ID
        or row.get("recipient_delivery_status") != "BOUNCED_NO_SUCH_USER_550_5_1_1"
        or row.get("gmail_label") != "SENT"
        or row.get("retry_authorized") is not False
    ):
        raise EvidenceHold("UNVERIFIED_BOUNCE_MESSAGE")
    return hashlib.sha256(raw).hexdigest()


def record_bounce(dsn: str, connect) -> str:
    """Return INSERTED or ALREADY_SUPPRESSED, with verified postcommit readback."""
    if not dsn.strip():
        raise EvidenceHold("EMPIREDB_DSN_UNAVAILABLE")
    with connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute("SET LOCAL lock_timeout = '3s'")
            cur.execute(
                "SELECT normalized_contact,contact_type,reason,source "
                "FROM public.outbound_suppressions "
                "WHERE lower(trim(normalized_contact))=%s FOR UPDATE",
                (RECIPIENT,),
            )
            original = cur.fetchall()
            if len(original) > 1:
                raise EvidenceHold("AMBIGUOUS_EXISTING_SUPPRESSION")
            if original:
                if original[0][1] != "email":
                    raise EvidenceHold("CONFLICTING_EXISTING_CONTACT_TYPE")
                disposition = "ALREADY_SUPPRESSED"
            else:
                cur.execute(
                    "INSERT INTO public.outbound_suppressions "
                    "(normalized_contact,contact_type,reason,source) "
                    "VALUES (%s,'email',%s,%s) "
                    "ON CONFLICT(normalized_contact) DO NOTHING",
                    (RECIPIENT, REASON, SOURCE),
                )
                disposition = "INSERTED"
            cur.execute(
                "SELECT normalized_contact,contact_type,reason,source "
                "FROM public.outbound_suppressions "
                "WHERE lower(trim(normalized_contact))=%s",
                (RECIPIENT,),
            )
            rows = cur.fetchall()
            if len(rows) != 1 or rows[0][1] != "email":
                raise EvidenceHold("TRANSACTION_READBACK_FAILED")
    with connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute(
                "SELECT normalized_contact,contact_type,reason,source "
                "FROM public.outbound_suppressions "
                "WHERE lower(trim(normalized_contact))=%s",
                (RECIPIENT,),
            )
            rows = cur.fetchall()
            if len(rows) != 1 or rows[0][1] != "email":
                raise EvidenceHold("POSTCOMMIT_READBACK_FAILED")
            if disposition == "INSERTED" and (
                rows[0][2] != REASON or rows[0][3] != SOURCE
            ):
                raise EvidenceHold("POSTCOMMIT_PROVENANCE_MISMATCH")
    return disposition


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--approved-gettradesmen-bounce", action="store_true")
    args = ap.parse_args(argv)
    try:
        proof_sha256 = verify_proof()
        if args.apply != args.approved_gettradesmen_bounce:
            raise EvidenceHold("TWO_PART_EXACT_APPROVAL_REQUIRED")
        if not args.apply:
            print(json.dumps({
                "status": "DRY_RUN_PROOF_VERIFIED", "recipient": RECIPIENT,
                "proof_sha256": proof_sha256, "database_write": False,
                "outbound_sent": False, "execution_authority": "none",
            }, sort_keys=True))
            return 0
        import psycopg
        disposition = record_bounce(os.getenv("EMPIREDB_DSN", ""), psycopg.connect)
        print(json.dumps({
            "status": disposition, "recipient": RECIPIENT,
            "reason": REASON, "source": SOURCE,
            "proof_sha256": proof_sha256, "canonical_readback_verified": True,
            "outbound_sent": False, "payment": False, "traffic_enabled": False,
        }, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "HELD_NO_CONFIRMED_SUPPRESSION",
            "reason_code": str(exc) if isinstance(exc, EvidenceHold)
                           else type(exc).__name__,
            "outbound_sent": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
