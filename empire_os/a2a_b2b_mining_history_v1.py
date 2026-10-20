"""Track changes to mined source evidence, not movements in actual buyers.

Small worktree-local history, max 90 snapshots. The history retains only
issuer-snapshot digests and aggregated research counts, not people/domains.
"""
from __future__ import annotations
from typing import Any, Mapping
from datetime import datetime
import re

from empire_os.a2a_b2b_evidence_mining_v1 import SCHEMA as MINING_SCHEMA

SCHEMA = "empire.a2a.business_evidence_mining_history.v1"
SOURCE_KEYS = frozenset((
    "buyer_public_research_seeds",
    "buyer_scout_research_window",
    "nyc_derived_permit_report",
))
_SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_SNAPSHOTS = 90


def _digests(mining: Mapping[str, Any]) -> dict[str, str] | None:
    if (not isinstance(mining, Mapping)
            or mining.get("schema_version") != MINING_SCHEMA
            or mining.get("execution_authority") != "NONE"
            or mining.get("verified_real_lead_count") != 0
            or mining.get("verified_new_local_buyer_count") != 0
            or mining.get("crm_write_performed") is not False):
        raise ValueError("UNTRUSTED_MINING_HISTORY_SOURCE")
    digest = mining.get("source_snapshot_digests_not_issuer_signatures")
    if digest is None and mining.get("source_mining_performed") is False:
        return None
    if (not isinstance(digest, Mapping) or set(digest) != SOURCE_KEYS
            or any(not isinstance(v, str) or not _SHA.fullmatch(v)
                   for v in digest.values())):
        raise ValueError("INVALID_MINING_SNAPSHOT_DIGESTS")
    return dict(sorted(digest.items()))


def update_mining_history(mining: Mapping[str, Any],
                          previous: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = _digests(mining)
    if previous is None:
        events: list[dict] = []
    elif (not isinstance(previous, Mapping)
          or previous.get("schema_version") != SCHEMA
          or previous.get("execution_authority") != "NONE"
          or not isinstance(previous.get("snapshots"), list)
          or len(previous["snapshots"]) > MAX_SNAPSHOTS):
        raise ValueError("UNTRUSTED_PREVIOUS_MINING_HISTORY")
    else:
        events = list(previous["snapshots"])
        for event in events:
            if (not isinstance(event, Mapping)
                    or not isinstance(event.get("source_snapshot_digests"), Mapping)
                    or set(event["source_snapshot_digests"]) != SOURCE_KEYS
                    or any(not isinstance(v, str) or not _SHA.fullmatch(v)
                           for v in event["source_snapshot_digests"].values())):
                raise ValueError("INVALID_PREVIOUS_MINING_HISTORY_EVENT")
    changed = []
    is_new = source is not None and (
        not events or source != events[-1]["source_snapshot_digests"])
    if is_new:
        last = events[-1]["source_snapshot_digests"] if events else {}
        changed = sorted(k for k in SOURCE_KEYS if last.get(k) != source[k])
        stamp = mining.get("generated_at")
        if not isinstance(stamp, str):
            raise ValueError("MISSING_MINING_REVIEW_TIMESTAMP")
        try:
            timestamp = datetime.fromisoformat(stamp)
        except ValueError:
            raise ValueError("INVALID_MINING_REVIEW_TIMESTAMP") from None
        if timestamp.tzinfo is None:
            raise ValueError("MINING_REVIEW_CLOCK_NOT_AWARE")
        targets = mining.get("target_mining_results")
        if not isinstance(targets, list) or len(targets) > 10:
            raise ValueError("UNTRUSTED_MINING_TARGET_RECORDS")
        summary = [
            {"sector": t["niche"], "market": t["requested_metro"],
             "sector_research_domains_not_buyers": t["public_business_research_record_count"]}
            for t in targets if isinstance(t, Mapping)
        ]
        if len(summary) != len(targets):
            raise ValueError("MALFORMED_MINING_TARGET_RECORD")
        events.append({
            "observed_at": stamp,
            "source_snapshot_digests": source,
            "source_input_counts": {
                "public_seeds": mining["public_seed_input_rows_scanned"],
                "current_scout_research_candidates": mining["buyer_scout_input_rows_scanned"],
                "distinct_business_research_domains": mining["distinct_public_business_domains_observed"],
            },
            "market_research_coverage": summary,
            "verified_new_buyers": 0,
            "verified_real_leads": 0,
        })
        events = events[-MAX_SNAPSHOTS:]
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "execution_authority": "NONE",
        "history_source_available": source is not None,
        "new_snapshot_appended": bool(is_new),
        "changed_source_families": changed,
        "snapshot_count": len(events),
        "snapshots": events,
        "owner_source_rotation_does_not_mean_demand_disappeared": True,
        "verified_customer_contacts_stored": False,
        "conversion_model_training_allowed": False,
        "crm_writes": 0, "outbound": False,
    }
