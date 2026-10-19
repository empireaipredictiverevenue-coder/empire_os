"""Reproducible v49 / V43 design shadow operator. No real user data."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json

from empire_os.flagship_legacy_v49_shadow import review_v49_matching_counterfactual
from empire_os.flagship_v43_novelty_shadow import review_v43_novelty_shadow


def _contractor(**changes):
    candidate = {
        "tenant_id": "fictional-tenant", "metro": "Dallas",
        "specialties": ["roofing"], "active": True,
        "trust_score": 8, "days_since_dispatch": 7,
        "active_dispatches": 1, "max_concurrent": 3,
        "territory_verified": True, "specialty_verified": True,
        "license_verified": True, "capacity_verified": True,
        "source_rights_verified": True, "trust_score_verified": True,
        "dispatch_history_verified": True, "suppressed": False,
    }
    candidate.update(changes)
    return candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic-only", action="store_true", required=True)
    opts = parser.parse_args()
    assert opts.synthetic_only
    matcher = review_v49_matching_counterfactual(
        lead={"tenant_id": "fictional-tenant", "metro": "Dallas",
              "specialties": ["roofing"], "approved_adjacent_metros": ["Plano"]},
        contractor_fixtures=[
            _contractor(),
            _contractor(metro="Los Angeles"),
            _contractor(specialties=["solar"]),
            _contractor(capacity_verified=False),
        ],
    )
    clock = datetime(2026, 10, 19, 18, tzinfo=timezone.utc)
    novelty = review_v43_novelty_shadow(
        observations=[{
            "source_digest_sha256": "b"*64,
            "source_observed_at": (clock-timedelta(hours=1)).isoformat(),
            "bloom_maybe_seen": True,
            "source_rights_verified": False,
            "conditional_etag_state": "UNKNOWN",
            "classifier_label": "UNDETERMINED",
            "classifier_independently_validated": False,
        }],
        exact_known_source_digests=["a"*64],
        as_of=clock,
    )
    assert matcher["legacy_ranked_count"] == 4
    assert matcher["fixture_research_eligible_count"] == 1
    assert matcher["commercial_allocations_authorized"] is False
    assert novelty["counts"]["bloom_maybe_positive_without_exact_confirmation"] == 1
    assert novelty["auto_dropping_new_sources"] is False
    print(json.dumps({
        "status": "SYNTHETIC_SHADOW_PASS",
        "legacy_v49": matcher,
        "v43_novelty": novelty,
        "test_fixtures_only": True,
        "real_payable_buyer_proven": False,
        "economic_accuracy_claim_authorized": False,
        "production_changed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
