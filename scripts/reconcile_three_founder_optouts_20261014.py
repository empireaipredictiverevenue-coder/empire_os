#!/usr/bin/env python3
"""Reconcile three explicitly evidenced founder-reply opt-outs in EmpireDB.

Read-only review by default. Applying requires exact founder approval and
root. Reuses the *existing* classify_outbound_reply SQL function to create
canonical suppressions. Zero email, payment, campaign, DNS, or provider writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from urllib.request import build_opener, HTTPRedirectHandler
from typing import Any

from empire_os.reply_opt_out_evidence import explicit_opt_out_from_preview

SCHEMA = "empire.founder.verified_optout_reconciliation.v1"
DB = "empiredb"
ACTOR = "founder_verified_three_optouts_20261014"
EVIDENCE = (
    ("07396f1e-f182-416d-b3de-3e5942cbbfa3", "b14bd6c9-e801-4de0-9b6b-232142c6c1a2",
     "david@gastleylaw.com"),
    ("59be5458-bd1f-4676-a35f-7a3021292ba4", "f992017f-628f-4253-aa19-14c0777585e1",
     "jason@ccdocs.com"),
    ("f044227f-25f8-4829-9378-04d0f6faab8a", "1e7a4142-be64-40f1-8d3e-0cc39cea1653",
     "dieter@atlantarc.net"),
)
_UUID = re.compile(r"^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$")


class SuppressionHeld(Exception):
    pass


def _root_required() -> None:
    if os.geteuid() != 0:
        raise SuppressionHeld("ROOT_ACCESS_REQUIRED")


def _postgres_sql(sql: str, *, read_output: bool) -> str:
    """Never log query text/provider payload; only parse bounded JSON."""
    _root_required()
    try:
        result = subprocess.run(
            ["runuser", "-u", "postgres", "--", "psql", "-X", "-q", "-A", "-t",
             "-v", "ON_ERROR_STOP=1", "-d", DB],
            input=sql, text=True, capture_output=True, timeout=20,
            check=False,
        )
        if result.returncode:
            raise SuppressionHeld("CANONICAL_POSTGRES_QUERY_FAILED")
        return result.stdout[:18000] if read_output else ""
    except SuppressionHeld:
        raise
    except Exception:
        raise SuppressionHeld("CANONICAL_POSTGRES_UNAVAILABLE") from None


def _select_sql() -> str:
    ids = ",".join("'" + reply_id + "'::uuid" for reply_id, _, _ in EVIDENCE)
    return f"""BEGIN READ ONLY;
SET LOCAL statement_timeout = '5s';
SELECT coalesce(json_agg(row_to_json(z)), '[]'::json)::text
FROM (
 SELECT r.id::text AS reply_id, r.intent_id::text AS intent_id,
        lower(btrim(r.normalized_from_contact)) AS sender,
        lower(btrim(i.normalized_recipient)) AS recipient,
        coalesce(r.subject, '') AS subject,
        coalesce(r.body_text, '') AS body_text,
        coalesce(r.classification, '') AS classification,
        i.status AS intent_status,
        (r.provider_message_id IS NOT NULL AND length(r.provider_message_id)>0) AS provider_id_present,
        s.contact_type AS suppression_contact_type
 FROM public.outbound_replies r
 JOIN public.outbound_intents i ON i.id=r.intent_id
 LEFT JOIN public.outbound_suppressions s
   ON lower(btrim(s.normalized_contact))=lower(btrim(i.normalized_recipient))
 WHERE r.id=ANY(ARRAY[{ids}])
 ORDER BY r.id
) z;
ROLLBACK;
"""


def _read() -> list[dict[str, Any]]:
    raw = _postgres_sql(_select_sql(), read_output=True).strip()
    try:
        values = json.loads(raw)
    except (ValueError, TypeError):
        raise SuppressionHeld("CANONICAL_REPLIES_READBACK_UNAVAILABLE") from None
    if not isinstance(values, list):
        raise SuppressionHeld("INVALID_CANONICAL_REPLIES_RESULT")
    return values


def validate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Fixed three known replies only. Identical recipient and intent lineage."""
    expected = {rid: (intent, email) for rid, intent, email in EVIDENCE}
    if len(rows) != len(expected):
        raise SuppressionHeld("MISSING_OR_DUPLICATED_OPT_OUT_REPLY")
    seen = set()
    outcome = []
    for row in rows:
        if not isinstance(row, dict):
            raise SuppressionHeld("UNTRUSTED_OPT_OUT_ROW")
        reply_id = str(row.get("reply_id", "")).lower()
        if reply_id in seen or reply_id not in expected:
            raise SuppressionHeld("UNEXPECTED_OR_DUPLICATE_OPT_OUT_REPLY")
        seen.add(reply_id)
        expected_intent, expected_email = expected[reply_id]
        if (row.get("intent_id") != expected_intent
                or row.get("sender") != expected_email
                or row.get("recipient") != expected_email
                or row.get("provider_id_present") is not True):
            raise SuppressionHeld("OPT_OUT_CONTACT_OR_INTENT_NOT_PROVEN")
        if row.get("classification") not in ("", "unclassified", "other", "unsubscribe"):
            raise SuppressionHeld("CONFLICTING_EXISTING_REPLY_CLASSIFICATION")
        if row.get("intent_status") not in ("sent", "delivered", "replied", "suppressed"):
            raise SuppressionHeld("OUTBOUND_INTENT_NOT_FROM_VALID_SENT_CHAIN")
        if row.get("suppression_contact_type") not in (None, "email"):
            raise SuppressionHeld("CONFLICTING_EXISTING_SUPPRESSION_TYPE")
        subject = row.get("subject")
        body = row.get("body_text")
        if not isinstance(subject, str) or not isinstance(body, str):
            raise SuppressionHeld("MISSING_CANONICAL_REPLY_TEXT")
        proof = explicit_opt_out_from_preview(subject, body)
        if proof["explicit_opt_out_observed"] is not True:
            raise SuppressionHeld("EXPLICIT_OPT_OUT_NOT_PROVEN")
        digest = hashlib.md5((subject + ":" + body).encode("utf-8")).hexdigest()
        outcome.append({
            "reply_id": reply_id, "intent_id": expected_intent,
            "recipient": expected_email, "digest": digest,
            "already_classified": row["classification"] == "unsubscribe",
            "already_suppressed": row["suppression_contact_type"] == "email",
            "evidence_kind": proof["evidence_kind"],
        })
    return {"proof_count": len(outcome), "rows": sorted(outcome, key=lambda d: d["reply_id"])}


def _apply_sql(proof: dict[str, Any]) -> str:
    evidence = proof["rows"]
    if len(evidence) != len(EVIDENCE):
        raise SuppressionHeld("NOT_EXACTLY_THREE_OPT_OUTS")
    tuples = []
    for row in evidence:
        rid = row["reply_id"]
        iid = row["intent_id"]
        email = row["recipient"]
        digest = row["digest"]
        if not _UUID.fullmatch(rid) or not _UUID.fullmatch(iid):
            raise SuppressionHeld("INVALID_CANONICAL_UUID")
        if not re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+", email) or not re.fullmatch(r"[a-f0-9]{32}", digest):
            raise SuppressionHeld("INVALID_OPT_OUT_PROOF_VALUE")
        tuples.append(f"('{rid}'::uuid, '{iid}'::uuid, '{email}', '{digest}')")
    values = ",\n".join(tuples)
    # The DO block acquires locks and revalidates all three proofs BEFORE any
    # updates. Any exception aborts the transaction atomically.
    return f"""BEGIN;
SET LOCAL ROLE empire_reply_ingest;
SET LOCAL statement_timeout='8s';
SET LOCAL lock_timeout='3s';
DO $optouts$
DECLARE r record; total integer:=0;
BEGIN
  FOR r IN
    SELECT reply.id AS reply_id, reply.intent_id, reply.subject,
           reply.body_text, reply.classification,
           reply.normalized_from_contact AS reply_sender,
           intent.normalized_recipient AS canonical_recipient,
           intent.status AS intent_status,
           proof.contact_email, proof.content_md5, proof.expected_intent
    FROM (VALUES {values})
       AS proof(reply_id, expected_intent, contact_email, content_md5)
    JOIN public.outbound_replies reply ON reply.id=proof.reply_id
    JOIN public.outbound_intents intent ON intent.id=reply.intent_id
    ORDER BY reply.id
    FOR UPDATE OF reply, intent
  LOOP
    total:=total+1;
    IF r.intent_id<>r.expected_intent
       OR lower(btrim(r.reply_sender))<>r.contact_email
       OR lower(btrim(r.canonical_recipient))<>r.contact_email
       OR md5(coalesce(r.subject,'') || ':' || coalesce(r.body_text,''))<>r.content_md5
       OR r.classification IS NOT NULL
          AND r.classification NOT IN ('unclassified','other','unsubscribe')
       OR r.intent_status NOT IN ('sent','delivered','replied','suppressed')
    THEN
       RAISE EXCEPTION 'optout proof mismatched at commit';
    END IF;
  END LOOP;
  IF total<>3 THEN RAISE EXCEPTION 'missing optout record'; END IF;
  PERFORM public.classify_outbound_reply('{EVIDENCE[0][0]}'::uuid,'unsubscribe',0.99,'{ACTOR}');
  PERFORM public.classify_outbound_reply('{EVIDENCE[1][0]}'::uuid,'unsubscribe',0.99,'{ACTOR}');
  PERFORM public.classify_outbound_reply('{EVIDENCE[2][0]}'::uuid,'unsubscribe',0.99,'{ACTOR}');
END $optouts$;
COMMIT;
"""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _dashboard_postcommit_check() -> bool:
    """Restart only the existing Founder API; never roll back legal opt-outs."""
    try:
        result = subprocess.run(
            ["systemctl", "restart", "empire-founder-dashboard-api.service"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=25, check=False,
        )
        if result.returncode != 0:
            return False
    except Exception:
        return False
    base = "http://127.0.0.1:8766/v1/founder-mailbox/threads/"
    opener = build_opener(_NoRedirect())
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        try:
            for _, intent_id, _ in EVIDENCE:
                with opener.open(base + intent_id + "?limit=50", timeout=4) as response:
                    if response.status != 200:
                        raise ValueError("DASHBOARD_NON_200")
                    data = json.loads(response.read(18000))
                if (data.get("classification") != "unsubscribe"
                        or data.get("suppressed") is not True
                        or data.get("execution_authority") != "none"):
                    return False
            return True
        except Exception:
            time.sleep(0.3)
    return False


def reconcile(*, apply: bool) -> dict[str, Any]:
    _root_required()
    first = validate(_read())
    counts = {
        "evidence_count": first["proof_count"],
        "already_suppressed_count": sum(x["already_suppressed"] for x in first["rows"]),
        "already_classified_count": sum(x["already_classified"] for x in first["rows"]),
        "database_writes": False,
        "email_sent": False,
        "outbound_enabled": False,
        "dns_changed": False,
    }
    if not apply:
        return {"status": "READ_ONLY_REVIEW_VERIFIED", **counts}
    if not all(x["already_suppressed"] and x["already_classified"] for x in first["rows"]):
        _postgres_sql(_apply_sql(first), read_output=False)
        counts["database_writes"] = True
    after = validate(_read())
    if not all(x["already_suppressed"] and x["already_classified"] for x in after["rows"]):
        raise SuppressionHeld("SUPPRESSION_POSTCOMMIT_READBACK_UNVERIFIED")
    refreshed = _dashboard_postcommit_check()
    return {
        "status": ("THREE_OPT_OUTS_CANONICALLY_SUPPRESSED" if refreshed
                   else "THREE_OPT_OUTS_SUPPRESSED_DASHBOARD_PENDING"),
        **counts, "canonical_readback_verified": True,
        "founder_dashboard_verified": refreshed,
        "unrelated_services_restarted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Precisely three canonical optouts; no email")
    p.add_argument("--review", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--approved-three-explicit-optouts-only", action="store_true")
    args = p.parse_args(argv)
    report = {
        "schema_version": SCHEMA, "status": "HELD",
        "mail_sent": False, "outbound_enabled": False, "dns_changed": False,
        "recipient_data_disclosed": False,
    }
    try:
        if args.apply == args.review:
            raise SuppressionHeld("CHOOSE_EXACTLY_ONE_OF_REVIEW_OR_APPLY")
        if args.apply and not args.approved_three_explicit_optouts_only:
            raise SuppressionHeld("EXPLICIT_THREE_CONTACT_SUPPRESSION_APPROVAL_REQUIRED")
        result = reconcile(apply=args.apply)
        report.update(result)
        print(json.dumps(report, sort_keys=True))
        return 0
    except SuppressionHeld as exc:
        report["reason_code"] = str(exc)
        print(json.dumps(report, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
