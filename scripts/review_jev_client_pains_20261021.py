#!/usr/bin/env python3
"""Owner-only offline Jev client-pain report from existing observations.

No network, database, browser automation, model calls, outbound or CRM writes.
The git-tracked receipt is aggregate only. Gitignored private review refs include
only the source URL and classification, never source text or contacts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from empire_os.jev_client_pain_discovery import (
    discover_client_pains, observations_from_existing_canonical_inbox,
)

LIVE_HISTORY = Path("/srv/empire_os/runtime/community_intent/observations.json")
CANONICAL_INBOX = Path("/srv/empire_os/runtime/acquisition/signal_inbox.json")
MAX_INPUT_BYTES = 12_000_000
REPORT = "JEV_CLIENT_PAIN_DISCOVERY_AGGREGATE_V2_20261021.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--input", type=Path, default=LIVE_HISTORY)
    parser.add_argument("--write-private", action="store_true")
    parser.add_argument("--canonical-inbox", type=Path, default=CANONICAL_INBOX)
    parser.add_argument("--no-canonical", action="store_true")
    args = parser.parse_args()
    path = args.input
    if (path.is_symlink() or not path.is_file()
        or not (0 < path.stat().st_size <= MAX_INPUT_BYTES)):
        raise ValueError("unsafe or oversized source")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or not isinstance(loaded.get("observations"), list):
        raise ValueError("original observations payload required")
    observed = list(loaded["observations"])
    canonical_count = 0
    if not args.no_canonical:
        cp = args.canonical_inbox
        if (cp.is_symlink() or not cp.is_file()
            or not (0 < cp.stat().st_size <= MAX_INPUT_BYTES)):
            raise ValueError("unsafe canonical inbox")
        canonical = json.loads(cp.read_text(encoding="utf-8"))
        inbound = observations_from_existing_canonical_inbox(canonical)
        canonical_count = len(inbound)
        observed.extend(inbound)
    result = discover_client_pains(
        observed,
        include_private_source_links=args.write_private,
    )
    repo = Path(__file__).resolve().parents[1]
    aggregate = {
        key: val for key, val in result.items() if key != "items"
    }
    aggregate["canonical_social_intent_rows_loaded"] = canonical_count
    aggregate["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    aggregate["source_scope"] = "existing_community_history_plus_canonical_social_intent"
    aggregate["verified_client_pain_points"] = 0
    aggregate["pain_taxonomy_candidates"] = len(result["pain_counts"])
    aggregate["identity_verification_required"] = True
    aggregate["commercial_matching_requires_owner_validation"] = True
    aggregate["contactable_prospects"] = 0
    aggregate["offer_review_counts"] = dict(sorted(Counter(
        offer
        for item in result["items"] if item["review_lane"] == "REVIEW_IDENTITY"
        for offer in item["matched_offers_to_validate"]
    ).items()))
    out = repo / "docs/commercial" / REPORT
    if out.is_symlink() or out.exists():
        raise ValueError("existing immutable public report; do not overwrite")
    with out.open("x", encoding="utf-8") as stream:
        json.dump(aggregate, stream, indent=2, sort_keys=True)
        stream.write("\n")
    if args.write_private:
        os.umask(0o077)
        private = repo / "runtime/jev_client_pain_discovery"
        private.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination = private / "private_latest.json"
        if destination.is_symlink():
            raise ValueError("unsafe private output symlink")
        tmp = private / "private_latest.json.tmp"
        with tmp.open("w", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(tmp, 0o600)
        tmp.replace(destination)
    print(json.dumps({
        "status": result["status"],
        "observations": result["observations_submitted"],
        "canonical_social_intent_loaded": canonical_count,
        "pain_hypotheses": result["pain_counts"],
        "lane_counts": result["review_lane_counts"],
        "private_queue_written": args.write_private,
        "canonical_prospects_verified": 0,
        "outreach_sent": 0,
        "execution_authority": "none",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
