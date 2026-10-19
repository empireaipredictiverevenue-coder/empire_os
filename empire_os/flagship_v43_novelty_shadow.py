"""V43 Precision Data Yield conceptual novelty experiment (SHADOW ONLY).

The supplied handoff describes V43 ETag freshness, Bloom prefilter and local
semantic classifier as UNVERIFIED designs. This is a no-network, no-storage
loss-prevention check on *synthetic* opaque digests, not implementation of
their claimed 70-90% savings or promotion of source rights.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence
import re

SCHEMA = "empire.flagship.v43_novelty_loss_shadow.v1"
HEX = re.compile(r"^[0-9a-f]{64}$")
MAX_ROWS = 250
MAX_AGE = timedelta(days=30)
STATES = frozenset(("NOT_MODIFIED", "CHANGED", "UNKNOWN"))


def _time(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 75:
        raise ValueError("source timestamp missing or unbounded")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError("original source timezone required")
    return parsed.astimezone(timezone.utc)


def review_v43_novelty_shadow(
    *, observations: Sequence[Mapping[str, Any]],
    exact_known_source_digests: Sequence[str],
    as_of: datetime,
) -> dict[str, Any]:
    """Pure fixture experiment: Bloom flags are NEVER sufficient to drop rows."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("review clock must be timezone aware")
    if not isinstance(observations, (list, tuple)) or len(observations) > MAX_ROWS:
        raise ValueError("bounded source experiment required")
    if (not isinstance(exact_known_source_digests, (list, tuple))
            or len(exact_known_source_digests) > 5000
            or any(not isinstance(key, str) or not HEX.fullmatch(key)
                   for key in exact_known_source_digests)
            or len(set(exact_known_source_digests)) != len(exact_known_source_digests)):
        raise ValueError("bounded exact digest inventory required")
    now = as_of.astimezone(timezone.utc)
    known = set(exact_known_source_digests)
    observed = set()
    counts = {
        "exact_known_reference": 0,
        "not_known_research_candidates": 0,
        "bloom_maybe_positive_without_exact_confirmation": 0,
        "bloom_false_negative_against_supplied_exact_inventory": 0,
        "source_rights_not_verified": 0,
        "source_timestamp_not_current": 0,
        "classifier_not_independently_validated": 0,
        "conditional_etag_not_modified_observation": 0,
    }
    for row in observations:
        if not isinstance(row, Mapping) or set(row) != {
            "source_digest_sha256", "source_observed_at",
            "bloom_maybe_seen", "source_rights_verified",
            "conditional_etag_state", "classifier_label",
            "classifier_independently_validated",
        }:
            raise ValueError("invalid source quality review shape")
        digest = row["source_digest_sha256"]
        if not isinstance(digest, str) or not HEX.fullmatch(digest) or digest in observed:
            raise ValueError("invalid or repeated source digest")
        observed.add(digest)
        if type(row["bloom_maybe_seen"]) is not bool:
            raise ValueError("Bloom observation must be boolean")
        if type(row["source_rights_verified"]) is not bool:
            raise ValueError("source rights must remain explicitly unknown/verified")
        if type(row["classifier_independently_validated"]) is not bool:
            raise ValueError("classifier evidence flag must be boolean")
        if row["conditional_etag_state"] not in STATES:
            raise ValueError("untrusted conditional HTTP state")
        if row["classifier_label"] not in ("RELEVANT", "IRRELEVANT", "UNDETERMINED"):
            raise ValueError("unsupported local classifier label")
        ts = _time(row["source_observed_at"])
        age = now-ts
        if not timedelta(0) <= age <= MAX_AGE:
            counts["source_timestamp_not_current"] += 1
        if row["source_rights_verified"] is not True:
            counts["source_rights_not_verified"] += 1
        if row["classifier_independently_validated"] is not True:
            counts["classifier_not_independently_validated"] += 1
        if row["conditional_etag_state"] == "NOT_MODIFIED":
            counts["conditional_etag_not_modified_observation"] += 1
        exact = digest in known
        if exact:
            counts["exact_known_reference"] += 1
            if not row["bloom_maybe_seen"]:
                counts["bloom_false_negative_against_supplied_exact_inventory"] += 1
        else:
            counts["not_known_research_candidates"] += 1
            if row["bloom_maybe_seen"]:
                # Correct behaviour: always exact-check before ever dropping.
                counts["bloom_maybe_positive_without_exact_confirmation"] += 1

    return {
        "schema_version": SCHEMA,
        "status": "SYNTHETIC_EVIDENCE_YIELD_SHADOW_ONLY",
        "mode": "OBSERVE",
        "source": "user_supplied_v43_design_handoff_20261019",
        "observed_fixture_count": len(observations),
        "counts": counts,
        "bloom_positive_is_not_duplicate_proof": True,
        "etag_not_modified_is_not_content_authenticity_proof": True,
        "classifier_label_not_ground_truth": True,
        "saved_crawl_costs_empirically_measured": False,
        "false_positive_rate_generalizes_to_production": False,
        "source_rights_authenticated_by_shadow": False,
        "customer_data_accessed": False,
        "actual_source_fetches": 0,
        "auto_dropping_new_sources": False,
        "search_producer_modified": False,
        "database_writes": False,
        "model_training": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
