#!/usr/bin/env python3
"""Aggregate-only classifier of a SAVED private TAM source review.

No canonical DB access, public search, website requests or record writes.
Prints no source URL, company name, person, entity or prospect identifiers.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path("/var/lib/empire/source-acquisition-review")
FILENAME = re.compile(r"20[0-9]{6}T[0-9]{6}Z-[0-9a-f]{12}\.json\Z")


def aggregate(packet: dict) -> dict:
    """Explain what can be inferred from the EXISTING packet, no new probes."""
    if (not isinstance(packet, dict)
        or packet.get("schema_version") != "empire.tam-first-party-discovery-review.v1"
        or packet.get("source") != "first_party_search"
        or packet.get("mode") != "OBSERVE"
        or packet.get("database_write") is not False
        or packet.get("acquisitions_appended") != 0
        or packet.get("outbound_sent") is not False
        or packet.get("execution_authority") != "none"):
        raise ValueError("unrecognised or non-observe private review packet")
    findings = packet.get("findings")
    attempted = packet.get("website_probes_attempted")
    if (not isinstance(findings, list)
        or not isinstance(attempted, int)
        or isinstance(attempted, bool)
        or not 0 <= attempted <= 5
        or not 0 <= len(findings) <= 5):
        raise ValueError("unsupported bounded review format")

    breakdown = Counter()
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("unrecognised review finding")
        state = finding.get("review_state")
        if state == "AMBIGUOUS_OR_MISSING_DISCOVERED_HOST":
            if finding.get("source_url") not in (None, ""):
                raise ValueError("unsupported ambiguous source receipt")
            breakdown["no_unique_website_candidate"] += 1
        elif state == "DISCOVERED_FIRST_PARTY_NAME_CORROBORATION_REVIEW":
            breakdown["company_name_supported_review_only"] += 1
        elif state == "DISCOVERED_SITE_IDENTITY_UNVERIFIED":
            if finding.get("source_url"):
                # The code only records source_url after a successful HTTPS,
                # same-host page receipt. Identity guard and/or exact name
                # did not pass, but cannot be reconstructed from this packet.
                breakdown["site_retrieved_but_identity_not_corroborated"] += 1
            else:
                breakdown["site_not_verified_from_expected_host"] += 1
        else:
            raise ValueError("unknown review state")

    result={
        "status":"SAVED_FIRST_PARTY_REVIEW_CLASSIFIED",
        "source":"first_party_search",
        "entities_selected_for_search":packet.get("entities_selected_for_search"),
        "search_candidates_before_filter":packet.get(
            "search_candidates_before_cross_entity_filter"),
        "site_probes_attempted":attempted,
        "review_findings":len(findings),
        "breakdown":dict(sorted(breakdown.items())),
        "country_verified":False,
        "source_urls_disclosed":0,
        "companies_disclosed":0,
        "contacts_disclosed":0,
        "new_network_calls":0,
        "new_database_queries":0,
        "new_database_writes":0,
        "acquisitions_appended":0,
        "outbound_sent":False,
    }
    if sum(breakdown.values()) != len(findings):
        raise ValueError("packet finding-count mismatch")
    return result


def classify_saved(filename: str, base: Path = ROOT) -> dict:
    if not FILENAME.fullmatch(filename):
        raise ValueError("invalid private packet filename")
    if base.is_symlink() or not base.is_dir():
        raise ValueError("private review folder unsafe")
    if base == ROOT and (base.stat().st_uid != 0
                        or base.stat().st_mode & 0o077):
        raise ValueError("private review directory permissions unsafe")
    path=base/filename
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("private review is not a regular file")
    if info.st_mode & 0o077 or (base==ROOT and info.st_uid!=0):
        raise ValueError("private review permissions unsafe")
    if info.st_size > 65536:
        raise ValueError("private review exceeds size bound")
    with path.open("r", encoding="utf-8") as stream:
        packet=json.load(stream)
    return aggregate(packet)


def main(argv=None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--packet",required=True,
                        help="Exact private review BASENAME, not a path")
    args=parser.parse_args(argv)
    if os.geteuid()!=0:
        raise ValueError("authorised root required for protected review")
    print(json.dumps(classify_saved(args.packet),sort_keys=True))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
        # Don't leak filenames, directory members or confidential content.
        print("PRIVATE_REVIEW_RESULT=BLOCKED",file=sys.stderr)
        raise SystemExit(3)
