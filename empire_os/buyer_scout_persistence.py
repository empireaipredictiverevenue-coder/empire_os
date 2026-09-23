"""Persist reconciled buyer-scout research candidates safely.

Only NEW_EXTERNAL_BUYER_CANDIDATE rows may be written to the Phase 4 holding
area. Persistence does not promote a candidate into prospects/buyers and grants
no outreach, terms, payment or revenue authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse


OUTPUT = Path("runtime/buyer_acquisition/persistence_latest.json")
RpcCall = Callable[[str, str, dict[str, Any]], Any]


def _host(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    parsed = urlparse(
        text if "://" in text else "https://" + text
    )
    host = parsed.netloc.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _scout_index(scout: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for raw in scout.get("candidates") or []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        domain = _host(row.get("website") or row.get("domain"))
        if domain:
            index[domain] = row
    return index


def persist_new_external_candidates(
    scout: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    *,
    rpc_call: RpcCall,
) -> dict[str, Any]:
    source = _scout_index(scout)
    persisted: list[dict[str, Any]] = []
    skipped = 0

    for raw in reconciliation.get("results") or []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        if row.get("reconciliation_state") != (
            "NEW_EXTERNAL_BUYER_CANDIDATE"
        ):
            skipped += 1
            continue

        domain = _host(row.get("domain"))
        candidate = source.get(domain)
        if not domain or candidate is None:
            skipped += 1
            continue

        website = str(candidate.get("website") or "").strip()
        if not website:
            skipped += 1
            continue

        site_evidence = {
            "site_evidence_score": candidate.get("site_evidence_score"),
            "first_party_email_count": candidate.get(
                "first_party_email_count"
            ),
            "first_party_phone_count": candidate.get(
                "first_party_phone_count"
            ),
            "people_count": candidate.get("people_count"),
            "first_party_emails": list(
                candidate.get("first_party_emails") or []
            )[:10],
            "first_party_phones": list(
                candidate.get("first_party_phones") or []
            )[:10],
            "first_party_people": [
                dict(person)
                for person in (
                    candidate.get("first_party_people") or []
                )[:10]
                if isinstance(person, Mapping)
            ],
            "direct_signal_hits": list(
                candidate.get("direct_signal_hits") or []
            ),
            "reseller_signal_hits": list(
                candidate.get("reseller_signal_hits") or []
            ),
        }
        provenance = {
            "source": "empire_buyer_acquisition_scout",
            "candidate_state": candidate.get("candidate_state"),
            "query_evidence_count": candidate.get(
                "query_evidence_count"
            ),
            "canonical_identity_verified": False,
            "commercial_terms_verified": False,
            "outreach_authorized": False,
        }

        payload = {
            "p_domain": domain,
            "p_business_name": candidate.get("business_name"),
            "p_website": website,
            "p_description": candidate.get("description"),
            "p_buyer_type": candidate.get("buyer_type") or "unknown",
            "p_direct_buyer_score": int(
                candidate.get("direct_buyer_score") or 0
            ),
            "p_explicit_direct_buyer_evidence": bool(
                candidate.get("explicit_direct_buyer_evidence")
            ),
            "p_target_buyer_pools": list(
                candidate.get("target_buyer_pools") or []
            ),
            "p_target_product_codes": list(
                candidate.get("target_product_codes") or []
            ),
            "p_target_corridor_keys": list(
                candidate.get("target_corridor_keys") or []
            ),
            "p_query_evidence": list(
                candidate.get("query_evidence") or []
            ),
            "p_site_evidence": site_evidence,
            "p_provenance": provenance,
            "p_actor": "empire_buyer_acquisition_scout",
        }
        response = rpc_call(
            "POST",
            "/rest/v1/rpc/propose_buyer_scout_candidate",
            payload,
        )
        persisted.append({
            "domain": domain,
            "response": response,
        })

    return {
        "schema_version": "empire.buyer_scout_persistence.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "persisted_candidate_count": len(persisted),
        "skipped_candidate_count": skipped,
        "persisted": persisted,
        "holding_area_only": True,
        "canonical_promotion_performed": False,
        "automatic_ingest_authorized": False,
        "outbound_sent": False,
        "terms_accepted": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def write_persistence(
    repo_root: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    root = Path(repo_root).resolve()
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path
