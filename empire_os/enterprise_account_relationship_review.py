"""Review known sponsor/portfolio links without merging account identity.

A public acquisition agreement does not authenticate its closing, decision
makers, prior contact history, buying intent, or outreach authority.
"""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.enterprise_public_market_role_review import market_role_review
from empire_os.predictive_revenue_enterprise_targets import TARGETS


def review_related_seed_accounts(domain: str) -> dict[str, Any]:
    """Join manually sourced company relationships to curated account keys.

    This is an evidence-backed internal research join, not an account merge.
    """
    role = market_role_review(domain)
    raw = role.get("related_seed_account_keys_for_dedup_review_only") or []
    if not isinstance(raw, (list, tuple)):
        raw = []
    seed_by_key = {target.account_key: target for target in TARGETS}
    linked = []
    unresolved = []
    for key in raw:
        account_key = str(key or "").strip()
        if not account_key or account_key in {x["account_key"] for x in linked}:
            continue
        target = seed_by_key.get(account_key)
        if not target:
            unresolved.append(account_key)
            continue
        linked.append({
            "account_key": account_key,
            "account_name": target.account_name,
            "review_relation": "ANNOUNCED_SPONSOR_TRANSACTION_LINK",
            "source_urls": [
                item["source_url"]
                for item in role.get("observations") or []
                if isinstance(item, Mapping)
                and "Blackstone" in str(item.get("fact") or "")
                and str(item.get("source_url") or "").startswith("https://")
            ],
        })
    if not linked and not unresolved:
        state = "NO_KNOWN_CURATED_SPONSOR_OVERLAP"
    elif unresolved:
        state = "UNRESOLVED_SPONSOR_KEY_REVIEW_REQUIRED"
    else:
        state = "RELATED_SPONSOR_HISTORY_REVIEW_REQUIRED"
    return {
        "status": state,
        "related_seed_accounts": linked,
        "unresolved_account_keys": unresolved,
        "transaction_closing_verified": False,
        "same_company_identity_verified": False,
        "duplicate_account_merge_authorized": False,
        "cross_account_contact_history_verified": False,
        "same_buyer_verified": False,
        "outreach_authorized": False,
        "execution_authority": "none",
    }
