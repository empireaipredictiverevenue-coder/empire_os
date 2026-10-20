"""Bounded local history of owner-source versions (not invented buyer facts).

History is driven by SHA-256 hashes of actual source bytes, not a newly
generated analysis timestamp. Re-reading identical evidence does not create a
new 'discovery'. No personal data or raw social discussions are copied.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping
import re

from empire_os.a2a_signal_decision_intelligence_v2 import SCHEMA as INTEL_SCHEMA

SCHEMA = "empire.a2a.source_evidence_history.v2"
_SOURCES = ("community", "gps", "catalogue", "nyc", "provenance")
_SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_SNAPSHOTS = 90


def merge_evidence_history(
    history: Mapping[str, Any] | None,
    *,
    source_hashes: Mapping[str, str],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    if (not isinstance(decision, Mapping)
            or decision.get("schema_version") != INTEL_SCHEMA
            or decision.get("execution_authority") != "NONE"
            or decision.get("verified_new_buyers") != 0
            or decision.get("outbound") is not False):
        raise ValueError("UNTRUSTED_DECISION_INTELLIGENCE")
    if (not isinstance(source_hashes, Mapping)
            or set(source_hashes) != set(_SOURCES)
            or any(not isinstance(source_hashes[k], str) or not _SHA.fullmatch(source_hashes[k])
                   for k in _SOURCES)):
        raise ValueError("INVALID_OWNER_SOURCE_DIGESTS")
    timestamp = decision.get("generated_at")
    if (not isinstance(timestamp, str)
            or not isinstance(decision.get("research_candidate_count"), int)
            or not isinstance(decision.get("changed_or_new_candidate_count"), int)):
        raise ValueError("INVALID_DECISION_HISTORY_FIELDS")
    try:
        if datetime.fromisoformat(timestamp).tzinfo is None:
            raise ValueError()
    except ValueError:
        raise ValueError("INVALID_DECISION_HISTORY_TIMESTAMP") from None
    if history is None:
        previous = []
    elif (not isinstance(history, Mapping)
          or history.get("schema_version") != SCHEMA
          or not isinstance(history.get("snapshots"), list)
          or len(history["snapshots"]) > MAX_SNAPSHOTS):
        raise ValueError("INVALID_PREVIOUS_EVIDENCE_HISTORY")
    else:
        previous = history["snapshots"]
        for entry in previous:
            if (not isinstance(entry, Mapping) or
                    not isinstance(entry.get("source_sha256"), Mapping) or
                    set(entry["source_sha256"]) != set(_SOURCES) or
                    not all(isinstance(entry["source_sha256"][k], str) and
                            _SHA.fullmatch(entry["source_sha256"][k])
                            for k in _SOURCES)):
                raise ValueError("CORRUPTED_PREVIOUS_SOURCE_HISTORY")
    hashes = dict(sorted(source_hashes.items()))
    new_snapshot = not previous or previous[-1]["source_sha256"] != hashes
    entries = list(previous)
    if new_snapshot:
        entries.append({
            "recorded_at": timestamp,
            "source_sha256": hashes,
            "research_candidates_at_review": decision["research_candidate_count"],
            "reported_changed_or_new_research_segments": decision["changed_or_new_candidate_count"],
            "data_product_catalogue_stale": decision.get("catalogue_stale") is True,
            "confirmed_new_buyers": 0,
            "confirmed_new_revenue": 0,
            "conversion_training_allowed": False,
        })
    entries = entries[-MAX_SNAPSHOTS:]
    changed = []
    if len(previous) and new_snapshot:
        changed = sorted(k for k in _SOURCES
                         if previous[-1]["source_sha256"][k] != hashes[k])
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE", "execution_authority": "NONE",
        "source_snapshots_recorded": len(entries),
        "new_source_snapshot_recorded_this_run": new_snapshot,
        "source_families_changed_since_previous_snapshot": changed,
        "identical_source_snapshot_seen_again": not new_snapshot,
        "snapshots": entries,
        "verified_person_or_buyer_identity_stored": False,
        "raw_group_posts_stored": False,
        "trained_on_inferred_conversions": False,
        "actual_revenue_inferred": False,
        "database_writes": False, "messages_sent": False,
    }
