#!/usr/bin/env python3
"""One-shot domain history for current review cohort and known sponsor link.

Requires EMPIREDB_DSN provided by an already authorised read-only environment.
Never prints credentials, recipient addresses or grants send-time clearance.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from empire_os.enterprise_domain_history_readonly import inspect_domains
from empire_os.predictive_revenue_enterprise_targets import TARGETS

REVIEW = Path("runtime/predictive_revenue/enterprise_commercial_review_latest.json")


def domains_from_review(review: dict) -> list[str]:
    if (not isinstance(review, dict) or review.get("mode") != "OBSERVE"
            or review.get("outreach_authorized") is not False):
        raise ValueError("UNTRUSTED_ENTERPRISE_REVIEW")
    packets = review.get("packets")
    if not isinstance(packets, list) or len(packets) > 15:
        raise ValueError("UNBOUNDED_ENTERPRISE_REVIEW")
    domains = set()
    seeds = {target.account_key: target for target in TARGETS}
    for row in packets:
        if not isinstance(row, dict) or row.get("outreach_authorized") is not False:
            raise ValueError("INVALID_ENTERPRISE_PACKET")
        domain = str(row.get("domain") or "").strip().lower()
        domains.add(domain)
        relation = row.get("sponsor_account_overlap_review") or {}
        for related in relation.get("related_seed_accounts") or []:
            if not isinstance(related, dict):
                raise ValueError("INVALID_RELATED_ACCOUNT")
            account = seeds.get(related.get("account_key"))
            if not account:
                raise ValueError("UNRESOLVED_SPONSOR_ACCOUNT")
            for source_url in account.evidence_urls:
                parts = urlsplit(source_url)
                if parts.scheme == "https" and parts.hostname:
                    host = parts.hostname.lower().removeprefix("www.")
                    domains.add(host)
                    break
    if not domains or len(domains) > 16:
        raise ValueError("INVALID_ENTERPRISE_DOMAIN_COHORT")
    return sorted(domains)


def main() -> int:
    try:
        root = Path("/srv/empire_os")
        review_path = root / REVIEW
        if review_path.is_symlink():
            raise ValueError("UNSAFE_ENTERPRISE_REVIEW_FILE")
        review = json.loads(review_path.read_text(encoding="utf-8"))
        result = inspect_domains(os.getenv("EMPIREDB_DSN", ""), domains_from_review(review))
    except Exception:
        print(json.dumps({
            "status": "HELD_CANONICAL_DOMAIN_HISTORY_UNAVAILABLE",
            "mode": "OBSERVE", "individual_recipient_suppression_cleared": False,
            "founder_send_authorized": False,
            "database_writes": False, "outbound_sent": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
