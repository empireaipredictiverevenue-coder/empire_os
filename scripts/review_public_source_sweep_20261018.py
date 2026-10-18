#!/usr/bin/env python3
"""Official-source sweep and explicitly requested, single-shot public probes.

Default: no network, read-only catalogue. Optional flags make at most
two *public* fixed-URL GETs. The separate --enqueue-internal-reviews flag
writes only to the EXISTING department queue, never production CRM/DB or
a new scheduler. No payment, secret, contact extraction or external send.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.public_source_sweep import (
    review_public_source_sweep, enqueue_deep_source_reviews,
)
from empire_os.ea_flood_source_observer import (
    observe_ea_flood_warnings, SourceObservationUnavailable,
)
from empire_os.uk_public_tender_observer import (
    observe_uk_public_tenders, PublicTenderSourceUnavailable,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="EmpireOS official source sweep")
    parser.add_argument("--probe-ea-flood", action="store_true")
    parser.add_argument("--probe-uk-tenders", action="store_true")
    parser.add_argument("--full-metadata", action="store_true")
    parser.add_argument("--enqueue-internal-reviews", action="store_true")
    args = parser.parse_args()
    catalogue = review_public_source_sweep()
    output = {
        "schema_version": catalogue["schema_version"],
        "reviewed_sources": catalogue["source_count"],
        "source_states": catalogue["by_readiness"],
        "top_new_public_source_choices": catalogue["top_new_public_source_choices"],
        "external_calls_requested": int(args.probe_ea_flood) + int(args.probe_uk_tenders),
        "automated_continuous_polling_enabled": False,
        "paid_api_calls": 0,
        "execution_authority": "none",
    }
    if args.full_metadata:
        output["catalogue"] = catalogue["sources"]
    if args.probe_ea_flood:
        try:
            flood = observe_ea_flood_warnings()
            output["ea_flood"] = {
                "status": flood["status"],
                "sample_size": flood["source_records_in_sample"],
                "severity_counts": flood["warning_severity_counts_in_sample"],
                "sample_at_limit": flood["sample_at_provider_limit"],
                "global_count_known": False,
                "physical_damage_or_buyer_proven": False,
            }
        except (SourceObservationUnavailable, ValueError) as exc:
            output["ea_flood"] = {
                "status": "SOURCE_UNAVAILABLE_OR_UNTRUSTED",
                "error_type": type(exc).__name__,
            }
    if args.probe_uk_tenders:
        try:
            tenders = observe_uk_public_tenders()
            output["uk_tenders"] = {
                "status": tenders["status"],
                "sample_size": tenders["record_count_in_bounded_page"],
                "vertical_cpv_matches": tenders["vertical_matches_in_page"],
                "published_tender_states": tenders["tender_status_counts_in_page"],
                "sample_at_limit": tenders["sample_at_limit"],
                "global_count_known": False,
                "contracts_won_or_revenue_proven": False,
            }
        except (PublicTenderSourceUnavailable, ValueError) as exc:
            output["uk_tenders"] = {
                "status": "SOURCE_UNAVAILABLE_OR_UNTRUSTED",
                "error_type": type(exc).__name__,
            }
    if args.enqueue_internal_reviews:
        output["internal_review_handoff"] = enqueue_deep_source_reviews(
            str(Path("/srv/empire_os")), catalogue,
        )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
