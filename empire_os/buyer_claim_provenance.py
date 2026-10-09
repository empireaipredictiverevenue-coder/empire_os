"""Bounded, auditable first-party buyer-demand claim receipts.

A first-party page is evidence of a statement, not proof of purchase orders,
budget, consent, terms, payment or outbound authority.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import re
from typing import Any, Mapping
from urllib.parse import urlsplit


_DIRECT = re.compile(
    r"\b(?:we|our (?:company|team|business))\s+"
    r"(?:currently\s+|actively\s+|regularly\s+)?"
    r"(?:buy|purchase|acquire|are buying|are purchasing|are acquiring)\s+"
    r"(?:(?:qualified|exclusive|live|inbound|third.party|verified)\s+){0,3}"
    r"(?:leads?|calls?|appointments?|pay.per.call\s+inventory)\b",
    re.IGNORECASE,
)
_NEGATED = re.compile(
    r"\b(?:we|our (?:company|team|business))\s+"
    r"(?:do not|don't|never|no longer|cannot|can't|will not|won't)\s+"
    r"(?:buy|purchase|acquire)\b",
    re.IGNORECASE,
)
_SUPPLIER = re.compile(
    r"\b(?:we\s+(?:generate|deliver|sell|provide|supply)\s+"
    r"(?:qualified\s+|exclusive\s+)?(?:leads?|calls?|appointments?)"
    r"|lead generation (?:agency|services?|platform))\b",
    re.IGNORECASE,
)
_INTERMEDIARY = re.compile(
    r"\b(?:we\s+(?:connect|match)\s+(?:publishers?|affiliates?|"
    r"advertisers?|buyers?|sellers?)|"
    r"lead (?:exchange|marketplace|broker)|affiliate network|"
    r"publisher network|resell (?:leads?|calls?)|"
    r"for (?:our\s+)?(?:clients|customers|advertisers))\b",
    re.IGNORECASE,
)


def _host(raw: str) -> str:
    try:
        url = urlsplit(raw)
        if (
            url.scheme not in {"http", "https"}
            or url.username is not None or url.password is not None
            or url.port not in {None, 80, 443}
        ):
            return ""
        return (url.hostname or "").casefold().rstrip(".").removeprefix("www.")
    except ValueError:
        return ""


def _sentences(text: str) -> list[str]:
    value = " ".join(text.split())[:8000]
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\s*;\s*", value) if s.strip()][:60]


def classify_buyer_source_pages(
    pages: list[Mapping[str, Any]], *, company_website: str,
    observed_at: str | None = None, max_pages: int = 5,
) -> dict[str, Any]:
    """Produce limited first-party receipts; reject external and mixed claims.

    Source URL and phrase are always attached. Does not scrape or mutate DB.
    """
    expected = _host(company_website)
    now = observed_at or datetime.now(timezone.utc).isoformat()
    receipts: list[dict[str, Any]] = []
    skipped = {"off_domain_or_invalid_url": 0, "no_visible_text": 0}
    for page in pages[:max(0, min(max_pages, 5))]:
        if not isinstance(page, Mapping):
            continue
        url = str(page.get("url") or "").strip()
        if not expected or _host(url) != expected:
            skipped["off_domain_or_invalid_url"] += 1
            continue
        raw = str(page.get("visible_text") or "")
        if not raw.strip():
            skipped["no_visible_text"] += 1
            continue
        sentences = _sentences(raw)
        supplier = any(_SUPPLIER.search(s) for s in sentences)
        intermediary = any(_INTERMEDIARY.search(s) for s in sentences)
        direct_sentences = [
            sentence for sentence in sentences
            if _DIRECT.search(sentence)
            and not _NEGATED.search(sentence)
            and not _INTERMEDIARY.search(sentence)
        ]
        if direct_sentences and not (supplier or intermediary):
            classification = "direct_inventory_buyer"
            claim_state = "first_party_explicit_purchase_observed"
        elif direct_sentences and (supplier or intermediary):
            classification = "mixed_role_requires_review"
            claim_state = "ambiguous_purchase_role"
        elif intermediary:
            classification = "intermediary_or_marketplace"
            claim_state = "no_direct_purchase_proof"
        elif supplier:
            classification = "lead_supplier_or_publisher"
            claim_state = "no_direct_purchase_proof"
        else:
            classification = "unknown"
            claim_state = "no_direct_purchase_proof"
        evidence_sentence = (
            direct_sentences[0] if direct_sentences
            else next((s for s in sentences if _INTERMEDIARY.search(s) or _SUPPLIER.search(s)), "")
        )
        receipts.append({
            "source_url": url,
            "company_domain": expected,
            "observed_at": now,
            "content_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "claim_excerpt": evidence_sentence[:220],
            "classification": classification,
            "claim_state": claim_state,
            "source_kind": "observed_first_party_page",
            "grants_outbound_authority": False,
        })
    role_types = {r["classification"] for r in receipts if r["classification"] != "unknown"}
    if "mixed_role_requires_review" in role_types or (
        "direct_inventory_buyer" in role_types
        and role_types.intersection({"intermediary_or_marketplace", "lead_supplier_or_publisher"})
    ):
        relationship = "mixed_role_requires_review"
    elif "direct_inventory_buyer" in role_types:
        relationship = "direct_inventory_buyer"
    elif "intermediary_or_marketplace" in role_types:
        relationship = "intermediary_or_marketplace"
    elif "lead_supplier_or_publisher" in role_types:
        relationship = "lead_supplier_or_publisher"
    else:
        relationship = "unknown"
    return {
        "schema_version": "empire.buyer_claim_provenance.v1",
        "buyer_relationship": relationship,
        "explicit_direct_purchase_observed": relationship == "direct_inventory_buyer",
        "claim_receipts": receipts[:5],
        "skipped_pages": skipped,
        "outbound_authorized": False,
        "database_write_performed": False,
    }


def unverified_direct_purchase_claim(row: Mapping[str, Any]) -> bool:
    """Protect historical REVIEW_READY rows from pre-contract buyer flags."""
    pools = row.get("target_buyer_pools") or []
    if not isinstance(pools, (list, tuple, set)):
        return True
    if row.get("explicit_direct_buyer_evidence") is not True:
        return False
    evidence = row.get("site_evidence")
    return not verified_direct_purchase_receipt(
        evidence if isinstance(evidence, Mapping) else {},
        company_website=str(row.get("website") or ""),
    )


def verified_direct_purchase_receipt(
    site_evidence: Mapping[str, Any], *, company_website: str,
    now: datetime | None = None, max_age_days: int = 30,
) -> bool:
    """Validate a stored receipt against its own excerpt and company domain.

    Content digest tracks source version, not cryptographic proof of authorship.
    """
    result = site_evidence.get("buyer_claim_provenance")
    if not isinstance(result, Mapping) or result.get("buyer_relationship") != "direct_inventory_buyer":
        return False
    packets = result.get("claim_receipts")
    if not isinstance(packets, list):
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return False
    current = current.astimezone(timezone.utc)
    for packet in packets[:5]:
        if not isinstance(packet, Mapping):
            continue
        if (
            packet.get("claim_state") != "first_party_explicit_purchase_observed"
            or packet.get("classification") != "direct_inventory_buyer"
            or packet.get("source_kind") != "observed_first_party_page"
            or _host(str(packet.get("source_url") or "")) != _host(company_website)
            or str(packet.get("company_domain") or "") != _host(company_website)
            or not _host(company_website)
        ):
            continue
        try:
            observed = datetime.fromisoformat(
                str(packet.get("observed_at") or "").replace("Z", "+00:00")
            )
            if observed.tzinfo is None:
                continue
            age = current - observed.astimezone(timezone.utc)
            if age > timedelta(days=max_age_days) or age < -timedelta(minutes=5):
                continue
        except (ValueError, TypeError, OverflowError):
            continue
        excerpt = str(packet.get("claim_excerpt") or "")
        content_hash = str(packet.get("content_sha256") or "")
        if (
            re.fullmatch(r"[a-f0-9]{64}", content_hash)
            and _DIRECT.search(excerpt) and not _NEGATED.search(excerpt)
            and not _INTERMEDIARY.search(excerpt)
        ):
            return True
    return False
