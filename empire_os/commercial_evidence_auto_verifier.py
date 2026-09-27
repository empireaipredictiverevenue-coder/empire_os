"""Bounded commercial-evidence standing authority.

Only evidence already constrained by the database's deterministic
auto_verify_buyer_stated_commercial_evidence RPC can be advanced. This worker
has no direct verify/reject privilege and no terms/payment/revenue authority.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping


Request = Callable[..., Any]


def run_commercial_evidence_auto_verifier(
    request: Request,
    *,
    limit: int = 25,
) -> dict[str, Any]:
    bounded = max(1, min(int(limit), 100))
    rows = request(
        "POST",
        "/rest/v1/rpc/list_auto_verifiable_commercial_evidence",
        payload={"p_limit": bounded},
    ) or []
    if isinstance(rows, Mapping):
        rows = [rows]
    if not isinstance(rows, list):
        raise ValueError("commercial evidence work projection must be a list")

    attempted = verified = existing = failed = 0
    results: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        evidence_id = str(row.get("evidence_id") or "").strip()
        if not evidence_id:
            failed += 1
            results.append({
                "evidence_id": None,
                "decision": "invalid_work_item",
            })
            continue

        attempted += 1
        try:
            result = request(
                "POST",
                "/rest/v1/rpc/auto_verify_buyer_stated_commercial_evidence",
                payload={"p_evidence_id": evidence_id},
            ) or {}
            decision = str(
                result.get("decision") if isinstance(result, Mapping) else ""
            )
            status = str(
                result.get("status") if isinstance(result, Mapping) else ""
            )
            if decision in {"verified", "existing_verification"} or status == "verified":
                if decision == "existing_verification":
                    existing += 1
                else:
                    verified += 1
            else:
                failed += 1
            results.append({
                "evidence_id": evidence_id,
                "decision": decision or "unknown",
                "status": status or None,
            })
        except Exception as exc:
            failed += 1
            results.append({
                "evidence_id": evidence_id,
                "decision": "verification_failed_closed",
                "error": f"{type(exc).__name__}:{str(exc)[:240]}",
            })

    return {
        "schema_version": "empire.commercial-evidence-auto-verifier.v1",
        "mode": "GUARDED_EXECUTE",
        "authority": "buyer_stated_price_deterministic_verification_only",
        "attempted": attempted,
        "verified": verified,
        "existing_verifications": existing,
        "failed_closed": failed,
        "terms_approved": False,
        "payment_mutation": False,
        "revenue_recognition": False,
        "ok": failed == 0,
        "results": results,
    }
