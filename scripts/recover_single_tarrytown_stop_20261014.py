#!/usr/bin/env python3
"""Recover one independently verified stop-contact reply into canonical EmpireDB.

Historical evidence source: the connected receiving account's GET received-email
record, inspected on 2026-10-14. Its authenticated provider metadata matches
the existing signed-webhook-derived canonical reply. Only the first visible
unquoted line ('Stop') is copied, NOT the sender's signature/quoted marketing.

Review is read-only. Apply is separately approved, root-only and transactionally
checks exact canonical row, sender, recipient, provider ID and content placeholder.
It reuses classify_outbound_reply to suppress; it never sends mail.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import stat
from pathlib import Path
from email.utils import parseaddr
from typing import Any

from empire_os.outbound_provider import inbound_fetch_error_code

REPLY_ID = "832ad81a-af22-4d81-aabc-6927e0875787"
INTENT_ID = "c77e459a-c3a9-4b0a-962a-e52c0f728bd9"
PROVIDER_ID = "44a5aec3-bb34-47c5-8a89-ab1eaeee0607"
CONTACT = "wolfgang@tarrytownroofing.com"
REPLY_ALIAS = "reply+" + INTENT_ID + "@mail.empire-ai.co.uk"
SUBJECT = "Re: James — quick idea for Tarrytown Roofing"
ORIGINAL_DATE = "2026-09-23"
VISIBLE_REPLY = "Stop"
ACTOR = "founder_provider_verified_reply_recovery_20261014"
SCHEMA = "empire.founder.single_reply_body_recovery.v1"

_UUID_RE = re.compile(r"^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$")


class RecoveryHeld(RuntimeError):
    pass


def _psql(script: str, *, read_output: bool) -> str:
    if os.geteuid() != 0:
        raise RecoveryHeld("ROOT_REQUIRED_FOR_CANONICAL_REPLY_REPAIR")
    try:
        proc = subprocess.run(
            ["runuser", "-u", "postgres", "--", "psql", "-X", "-q", "-A", "-t",
             "-v", "ON_ERROR_STOP=1", "-d", "empiredb"],
            input=script, text=True, capture_output=True, timeout=20, check=False,
        )
        if proc.returncode != 0:
            raise RecoveryHeld("CANONICAL_LOCAL_POSTGRES_PROBE_FAILED")
        return proc.stdout[:12000] if read_output else ""
    except RecoveryHeld:
        raise
    except Exception:
        raise RecoveryHeld("CANONICAL_POSTGRES_CONNECTION_UNAVAILABLE") from None


def _review_sql() -> str:
    return f"""BEGIN READ ONLY;
SET LOCAL statement_timeout = '5000ms';
SELECT row_to_json(x)::text FROM (
  SELECT r.id::text AS reply_id,
         r.intent_id::text AS intent_id,
         r.provider_message_id AS provider_id,
         lower(btrim(r.normalized_from_contact)) AS sender,
         lower(btrim(i.normalized_recipient)) AS recipient,
         r.subject AS subject,
         (r.received_at at time zone 'UTC')::date::text AS date_utc,
         CASE WHEN r.body_text='[provider body unavailable]' THEN 'PLACEHOLDER'
              WHEN r.body_text='Stop' THEN 'STOP'
              ELSE 'UNEXPECTED' END AS body_state,
         r.classification AS classification,
         i.status AS intent_status,
         r.metadata->>'provider' AS provider,
         r.metadata->>'body_unavailable' AS body_unavailable,
         (SELECT count(*) FROM public.outbound_suppressions s
          WHERE lower(btrim(s.normalized_contact))=lower(btrim(i.normalized_recipient))
            AND s.contact_type='email') AS suppression_count
  FROM public.outbound_replies r
  JOIN public.outbound_intents i ON i.id=r.intent_id
  WHERE r.id='{REPLY_ID}'::uuid
) x;
ROLLBACK;
"""


def _read() -> dict[str, Any]:
    raw = _psql(_review_sql(), read_output=True).strip()
    try:
        d = json.loads(raw)
    except (ValueError, TypeError):
        raise RecoveryHeld("CANONICAL_REPLY_PROOF_UNAVAILABLE") from None
    if not isinstance(d, dict):
        raise RecoveryHeld("CANONICAL_REPLY_PROOF_MISSING")
    return d


def check_proof(d: dict[str, Any]) -> dict[str, Any]:
    """Provider identity checked against exactly one signed-webhook DB row."""
    if not isinstance(d, dict):
        raise RecoveryHeld("INVALID_RECOVERY_PROOF")
    expected = {
        "reply_id": REPLY_ID,
        "intent_id": INTENT_ID,
        "provider_id": PROVIDER_ID,
        "sender": CONTACT,
        "recipient": CONTACT,
        "subject": SUBJECT,
        "date_utc": ORIGINAL_DATE,
        "provider": "resend",
    }
    if any(d.get(k) != v for k, v in expected.items()):
        raise RecoveryHeld("PROVIDER_AND_CANONICAL_REPLY_IDENTITY_MISMATCH")
    if (d.get("body_state") not in ("PLACEHOLDER", "STOP")
            or d.get("classification") not in ("unclassified", "unsubscribe")
            or d.get("intent_status") not in ("sent", "delivered", "replied", "suppressed")
            or d.get("suppression_count") not in (0, 1)):
        raise RecoveryHeld("CANONICAL_REPLY_OR_SUPPRESSION_STATE_UNEXPECTED")
    if d["body_state"] == "PLACEHOLDER" and d.get("body_unavailable") not in ("true", "True"):
        raise RecoveryHeld("SOURCE_MISSING_BODY_FLAG_UNVERIFIED")
    if (d["body_state"] == "STOP"
            and (d["classification"] != "unsubscribe"
                 or d["suppression_count"] != 1)):
        raise RecoveryHeld("PARTIALLY_RECOVERED_RECORD_NEEDS_MANUAL_REVIEW")
    return {
        "source": "SIGNED_CANONICAL_REPLY_PLUS_CONNECTED_PROVIDER_GET",
        "provider_identity_verified": True,
        "same_contact_as_outbound_recipient": True,
        "body_state": d["body_state"],
        "canonical_suppression_verified": d["suppression_count"] == 1,
        "classification": d["classification"],
        "ready_for_exact_recovery": d["body_state"] == "PLACEHOLDER",
    }


def _apply_sql() -> str:
    # Fixed, audited, exact-reply SQL. All interpolated values are compile-time
    # constants and must match their explicitly verified literal contracts.
    for value in (REPLY_ID, INTENT_ID, PROVIDER_ID):
        if not _UUID_RE.fullmatch(value):
            raise RecoveryHeld("INVALID_PINNED_PROVIDER_ID")
    if VISIBLE_REPLY != "Stop" or re.search(r"[^a-zA-Z0-9@.\-]", CONTACT):
        raise RecoveryHeld("PINNED_EVIDENCE_CHANGED")
    return f"""BEGIN;
SET LOCAL ROLE empire_reply_ingest;
SET LOCAL statement_timeout = '8000ms';
SET LOCAL lock_timeout = '3000ms';
DO $recovery$
DECLARE r record; existing_suppression integer;
BEGIN
  SELECT reply.id, reply.intent_id, reply.provider_message_id,
         reply.normalized_from_contact, reply.subject, reply.body_text,
         reply.classification, reply.received_at,
         reply.metadata, intent.normalized_recipient, intent.status
    INTO r
    FROM public.outbound_replies reply
    JOIN public.outbound_intents intent ON intent.id=reply.intent_id
    WHERE reply.id='{REPLY_ID}'::uuid
    FOR UPDATE OF reply,intent;
  IF NOT FOUND THEN RAISE EXCEPTION 'pinned reply not present'; END IF;
  IF r.intent_id<>'{INTENT_ID}'::uuid
     OR r.provider_message_id<>'{PROVIDER_ID}'
     OR lower(btrim(r.normalized_from_contact))<>'{CONTACT}'
     OR lower(btrim(r.normalized_recipient))<>'{CONTACT}'
     OR r.subject<>'{SUBJECT}'
     OR (r.received_at at time zone 'UTC')::date<>'{ORIGINAL_DATE}'::date
     OR r.body_text<>'[provider body unavailable]'
     OR r.classification<>'unclassified'
     OR coalesce(r.metadata->>'body_unavailable','')<>'true'
     OR coalesce(r.metadata->>'provider','')<>'resend'
     OR r.status NOT IN ('sent','delivered','replied')
  THEN RAISE EXCEPTION 'pinned provider reply evidence mismatch'; END IF;
  UPDATE public.outbound_replies
     SET body_text='{VISIBLE_REPLY}',
         metadata=metadata || jsonb_build_object(
            'body_unavailable',false,
            'body_recovery_source','connected_resend_received_email_get_20261014',
            'body_recovery_mode','unquoted_visible_reply_only',
            'body_recovered_at',clock_timestamp(),
            'untrusted_content',true,
            'executable',false
         )
   WHERE id='{REPLY_ID}'::uuid;
  PERFORM public.classify_outbound_reply(
      '{REPLY_ID}'::uuid,'unsubscribe',0.99,'{ACTOR}');
END $recovery$;
COMMIT;
"""


def _probe_live_receiving_credential() -> str:
    """Read-only GET using exactly the credential configured for live inbound.

    A failed probe never results in an email send or any credential disclosure.
    The fallback repair relies on separately verified linked-account evidence.
    """
    if os.geteuid() != 0:
        return "ROOT_REQUIRED"
    secret_path = Path("/srv/empire_os/runtime/secrets/outbound.env")
    try:
        meta = secret_path.stat()
        if (secret_path.is_symlink() or not secret_path.is_file()
                or stat.S_IMODE(meta.st_mode) & 0o077):
            return "INBOUND_CREDENTIAL_FILE_UNTRUSTED"
        from dotenv import dotenv_values
        cfg = dotenv_values(secret_path)
        receiving_key = str(cfg.get("RESEND_RECEIVING_API_KEY") or "").strip()
        fallback_key = str(cfg.get("RESEND_API_KEY") or "").strip()
        key = receiving_key or fallback_key
        if not key:
            return "INBOUND_RECEIVING_CREDENTIAL_NOT_CONFIGURED"
        import resend
        resend.api_key = key  # process-local SDK setting; never sent to stdout
        payload = resend.Emails.Receiving.get(PROVIDER_ID)
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            payload = payload["data"]
        if not isinstance(payload, dict):
            return "RECEIVING_RESPONSE_SCHEMA_UNEXPECTED"
        sender = parseaddr(str(payload.get("from") or ""))[1].lower()
        recipients = payload.get("to") or payload.get("received_for") or []
        if isinstance(recipients, str):
            recipients = [recipients]
        emails = [parseaddr(str(x))[1].lower() for x in recipients]
        visible = str(payload.get("text") or "").strip().splitlines()
        first_line = next((line.strip() for line in visible if line.strip()), "")
        if (sender != CONTACT or REPLY_ALIAS not in emails
                or str(payload.get("subject") or "") != SUBJECT
                or first_line.casefold() != "stop"):
            return "RECEIVED_PROVIDER_BODY_OR_IDENTITY_CONFLICT"
        return "LIVE_SERVER_RECEIVING_READ_VERIFIED"
    except Exception as exc:
        return inbound_fetch_error_code(exc)


def restore(*, apply: bool) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise RecoveryHeld("ROOT_REQUIRED_FOR_CANONICAL_REPLY_REPAIR")
    before = check_proof(_read())
    provider_probe = _probe_live_receiving_credential()
    if provider_probe == 'RECEIVED_PROVIDER_BODY_OR_IDENTITY_CONFLICT':
        raise RecoveryHeld('LIVE_PROVIDER_RECORD_CONFLICT_REQUIRES_REVIEW')
    result = {
        "schema_version": SCHEMA,
        "status": "REVIEW_ONLY",
        "source": before["source"],
        "live_inbound_receiving_probe": provider_probe,
        "provider_identity_verified": True,
        "canonical_suppression_verified": before["canonical_suppression_verified"],
        "body_state_before": before["body_state"],
        "database_writes": False,
        "email_sent": False,
        "dns_changed": False,
        "outbound_enabled": False,
        "provider_email_content_logged": False,
    }
    if not apply:
        return result
    if before["ready_for_exact_recovery"]:
        _psql(_apply_sql(), read_output=False)
        result["database_writes"] = True
    after = check_proof(_read())
    if (after["body_state"] != "STOP"
            or after["classification"] != "unsubscribe"
            or after["canonical_suppression_verified"] is not True):
        raise RecoveryHeld("CANONICAL_POSTCOMMIT_RECOVERY_UNVERIFIED")
    result["status"] = "WOLFGANG_STOP_RECOVERED_AND_SUPPRESSED"
    result["canonical_suppression_verified"] = True
    result["body_state_after"] = "STOP"
    result["no_contact_enforced"] = True
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="One verified sender stop-contact recovery")
    p.add_argument("--review", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--approved-wolfgang-stop-only", action="store_true")
    args = p.parse_args(argv)
    if args.apply == args.review:
        print(json.dumps({"status": "HELD", "reason_code": "CHOOSE_REVIEW_OR_EXACT_APPROVED_APPLY",
                          "email_sent": False}, sort_keys=True))
        return 2
    if args.apply and not args.approved_wolfgang_stop_only:
        print(json.dumps({"status": "HELD", "reason_code": "EXACT_RECIPIENT_APPROVAL_REQUIRED",
                          "email_sent": False}, sort_keys=True))
        return 2
    try:
        data = restore(apply=args.apply)
        print(json.dumps(data, sort_keys=True))
        return 0
    except RecoveryHeld as error:
        print(json.dumps({
            "status": "HELD", "reason_code": str(error),
            "email_sent": False, "outbound_enabled": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
