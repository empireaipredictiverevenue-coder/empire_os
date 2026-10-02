#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import urllib.parse

import psycopg

from empire_os.buyer_scout_review_readiness import materialize_review_readiness
from empire_os.mx_validator import MxValidator
from empire_os.offer_contact_holding_bridge import build_holding_candidates
from empire_os.sb import request_json


ROOT = Path("/srv/empire_os")
SOURCE = (
    ROOT / "runtime/predictive_revenue/commercial_offer_book/"
    "contact_recovery_observed.json"
)
OUTPUT = ROOT / "runtime/buyer_acquisition/offer_contact_holding_latest.json"


def _all_emails(recovery: dict) -> list[str]:
    return sorted({
        str(contact.get("email") or "").strip().lower()
        for item in recovery.get("items") or []
        if isinstance(item, dict)
        for contact in item.get("person_bound_candidates") or []
        if isinstance(contact, dict)
        and str(contact.get("email") or "").strip()
    })


def _mx_rows(emails: list[str]) -> list[dict]:
    def validate(email: str) -> dict:
        result = MxValidator(
            smtp_timeout=2,
            do_smtp_probe=False,
        ).validate(email)
        return {
            "email": email,
            "is_valid": bool(result.is_valid),
            "has_mx": bool(result.has_mx),
            "is_role_address": bool(result.is_role_address),
            "is_disposable": bool(result.is_disposable),
            "confidence": float(result.confidence or 0.0),
            "smtp_status": result.smtp_status,
            "execution_authority": "none",
        }

    rows = []
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(emails)))) as pool:
        futures = [pool.submit(validate, email) for email in emails]
        for future in as_completed(futures):
            rows.append(future.result())
    return sorted(rows, key=lambda row: row["email"])


def _suppressed(emails: list[str]) -> set[str]:
    dsn = os.environ.get("EMPIREDB_DSN", "").strip()
    if not dsn or not emails:
        return set()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                """
                SELECT normalized_contact
                FROM public.outbound_suppressions
                WHERE normalized_contact=ANY(%s)
                """,
                (emails,),
            )
            return {
                str(row[0] or "").strip().lower()
                for row in cur.fetchall()
                if str(row[0] or "").strip()
            }


def _persist_candidate(candidate: dict) -> dict:
    payload = {
        "p_domain": candidate["domain"],
        "p_business_name": candidate["business_name"],
        "p_website": candidate["website"],
        "p_description": candidate["description"],
        "p_buyer_type": candidate["buyer_type"],
        "p_direct_buyer_score": candidate["direct_buyer_score"],
        "p_explicit_direct_buyer_evidence": (
            candidate["explicit_direct_buyer_evidence"]
        ),
        "p_target_buyer_pools": candidate["target_buyer_pools"],
        "p_target_product_codes": candidate["target_product_codes"],
        "p_target_corridor_keys": candidate["target_corridor_keys"],
        "p_query_evidence": candidate["query_evidence"],
        "p_site_evidence": candidate["site_evidence"],
        "p_provenance": candidate["provenance"],
        "p_actor": "offer_contact_holding_bridge",
    }
    result = request_json(
        "POST",
        "/rest/v1/rpc/propose_buyer_scout_candidate",
        payload=payload,
    )
    if not isinstance(result, dict):
        raise RuntimeError("holding candidate RPC evidence missing")
    if result.get("decision") != "candidate_recorded":
        raise RuntimeError("holding candidate RPC decision invalid")
    return dict(result)


def _candidate_row(candidate_id: str) -> dict | None:
    query = urllib.parse.urlencode({
        "select": (
            "id,domain,business_name,website,buyer_type,"
            "direct_buyer_score,explicit_direct_buyer_evidence,"
            "target_buyer_pools,target_product_codes,target_corridor_keys,"
            "query_evidence,site_evidence,reconciliation_state,review_state"
        ),
        "id": f"eq.{candidate_id}",
        "limit": "1",
    })
    rows = request_json(
        "GET",
        "/rest/v1/buyer_scout_candidates?" + query,
    ) or []
    return dict(rows[0]) if rows and isinstance(rows[0], dict) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

    recovery = json.loads(SOURCE.read_text(encoding="utf-8"))
    emails = _all_emails(recovery)
    mx_rows = _mx_rows(emails)
    suppressed = _suppressed(emails)
    bridge = build_holding_candidates(
        recovery,
        mx_rows=mx_rows,
        suppressed_emails=suppressed,
    )

    persisted = []
    readiness = {
        "candidate_count": 0,
        "review_ready_count": 0,
        "database_write_performed": False,
    }
    if args.persist:
        touched = []
        for candidate in bridge["candidates"]:
            response = _persist_candidate(candidate)
            persisted.append({
                "domain": candidate["domain"],
                "response": response,
            })
            candidate_id = str(response.get("candidate_id") or "").strip()
            if candidate_id:
                row = _candidate_row(candidate_id)
                if row is not None:
                    touched.append(row)

        readiness = materialize_review_readiness(
            touched,
            patch_call=lambda method, path, body: request_json(
                method,
                path,
                payload=body,
                prefer="return=representation",
            ),
        )

    payload = {
        **bridge,
        "mx_rows": mx_rows,
        "suppressed_emails": sorted(suppressed),
        "persist_requested": bool(args.persist),
        "persisted": persisted,
        "persisted_candidate_count": len(persisted),
        "review_readiness": readiness,
        "database_write_performed": bool(args.persist and persisted),
        "canonical_promotion_performed": False,
        "founder_promotion_required": bool(
            args.persist and readiness.get("review_ready_count", 0)
        ),
        "outbound_authorized": False,
        "actual_revenue": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(OUTPUT)

    print(json.dumps({
        "ok": True,
        "verified_contact_count": bridge["verified_contact_count"],
        "candidate_count": bridge["candidate_count"],
        "blocked_company_count": bridge["blocked_company_count"],
        "suppressed_count": len(suppressed),
        "persisted_candidate_count": len(persisted),
        "review_ready_count": readiness.get("review_ready_count", 0),
        "canonical_promotion_performed": False,
        "founder_promotion_required": payload["founder_promotion_required"],
        "outbound_authorized": False,
        "actual_revenue": False,
        "output": str(OUTPUT),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
