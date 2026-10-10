#!/usr/bin/env python3
"""Source acquisition matching for existing TAM entities: review-only.

Public-source retrieval + read-only canonical query; NO database inserts.
Prints aggregate counts. Sensitive review proposals saved root-private only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone
from uuid import uuid4

from empire_os.runtime_env import load_runtime_env
from empire_os.tam_source_acquisition_connector import (
    canonical_targets, source_observations, build_review,
    build_first_party_site_review, build_first_party_discovery_review,
    build_recc_source_first_review,
    validate_scope, MAX_TARGETS, MAX_SOURCE,
)

REPORT_DIR=Path("/var/lib/empire/source-acquisition-review")


def save_private(packet: dict, folder: Path=REPORT_DIR) -> Path:
    if folder.is_symlink():
        raise RuntimeError("private review folder is a symlink")
    folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    if (folder.is_symlink() or folder.stat().st_mode & 0o077
            or (os.geteuid()==0 and folder.stat().st_uid!=0)):
        raise RuntimeError("private review directory unsafe")
    filename=(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
              +"-"+uuid4().hex[:12]+".json")
    dest=folder/filename
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW
    fd=os.open(dest,flags,0o600)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(packet,stream,indent=2,sort_keys=True,default=str)
            stream.write("\n")
        os.chmod(dest,0o600)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest


def main(argv=None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--observe",action="store_true",required=True)
    parser.add_argument("--source",choices=("recc_solar","overpass_osm","first_party_site","first_party_search","recc_source_first"),
                        required=True)
    parser.add_argument("--sector",choices=("solar","roofing"),required=True)
    parser.add_argument("--country",choices=("GB","US"),required=True)
    parser.add_argument("--metro")
    parser.add_argument("--max-targets",type=int,default=250)
    parser.add_argument("--max-source",type=int,default=40)
    parser.add_argument("--source-page",type=int,default=0)
    parser.add_argument("--page-count",type=int,default=1)
    parser.add_argument("--diagnose-only",action="store_true")
    parser.add_argument("--max-site-probes",type=int,default=2)
    args=parser.parse_args(argv)
    validate_scope(source=args.source,sector=args.sector,
                   country=args.country,limit=args.max_targets)
    if not 1 <= args.max_source <= MAX_SOURCE:
        parser.error("source observation limit out of bounds")
    if args.source=="first_party_search" and (
            args.max_source > 5 or args.page_count != 1
            or args.source_page != 0 or args.metro):
        parser.error("first-party discovery permits at most five entities")
    if args.source=="recc_source_first" and (
            args.max_source > 5
            or not 1 <= args.max_site_probes <= 2
            or args.page_count != 1 or args.source_page != 0
            or args.metro or args.diagnose_only):
        parser.error("source-first review restricted to five members and two sites")
    if args.diagnose_only and args.source!="first_party_site":
        parser.error("--diagnose-only is only for first-party identity eligibility")
    if (args.source=="first_party_site" and
            (args.max_source > 5 or args.page_count != 1
             or args.source_page != 0 or args.metro)):
        parser.error("first-party website review permits five public sites only")
    if (not 1 <= args.page_count <= 3
            or args.source_page < 0
            or args.source_page+args.page_count-1 > 40
            or (args.source != "recc_solar" and args.page_count != 1)):
        parser.error("bounded source page sweep requires RECC, 1-3 pages")
    if os.geteuid()!=0:
        raise SystemExit("source acquisition connector requires authorised root")
    if args.source=="recc_source_first":
        packet=build_recc_source_first_review(
            max_members=args.max_source,
            max_site_probes=args.max_site_probes,
        )
        location=save_private(packet)
        print(json.dumps({
            "status":"PUBLIC_RECC_SOURCE_FIRST_REVIEW_PREPARED",
            "source":"recc_solar","country_source":"GB",
            "members_listed":packet["members_listed"],
            "canonical_acquisition_previews":packet["canonical_acquisition_previews"],
            "public_sites_probed":packet["public_sites_probed"],
            "first_party_identity_supported_review_count":packet[
                "first_party_identity_supported_review_count"],
            "member_postcodes_present":packet["member_postcodes_present"],
            "review_holds":packet["review_holds"],
            "private_review_file":str(location),
            "existing_canonical_duplicate_check_performed":False,
            "database_queries":0,"database_writes":0,
            "prospects_created":0,"acquisitions_appended":0,
            "outbound_sent":False,"execution_authority":"none",
        },sort_keys=True))
        return 0
    env=load_runtime_env("/etc/empiredb.env",required=("EMPIREDB_DSN",))
    targets=canonical_targets(env["EMPIREDB_DSN"],
                              sector=args.sector,limit=args.max_targets)
    if args.source=="first_party_site":
        packet=build_first_party_site_review(
            targets=targets,max_sites=args.max_source,
            diagnose_only=args.diagnose_only,
        )
        packet["target_query_limit"]=args.max_targets
        packet["target_selection_complete"]=False
        path=save_private(packet)
        print(json.dumps({
            "status":(
                "READ_ONLY_FIRST_PARTY_ELIGIBILITY_DIAGNOSTIC"
                if args.diagnose_only
                else "READ_ONLY_FIRST_PARTY_EVIDENCE_REVIEW_PREPARED"
            ),
            "source":"first_party_site","country_focus":"GB",
            "entities_considered":packet["entities_considered"],
            "entities_with_unique_business_host":packet[
                "entities_with_unique_business_host"],
            "entities_skipped_for_ambiguous_identity_or_domain":packet[
                "entities_skipped_for_ambiguous_identity_or_domain"],
            "eligibility_diagnostic":packet["eligibility_diagnostic"],
            "diagnose_only":args.diagnose_only,
            "site_probes_attempted":packet["site_probes_attempted"],
            "sites_retrieved_from_expected_host":packet[
                "sites_retrieved_from_expected_host"],
            "sites_supporting_exact_canonical_name":packet[
                "sites_supporting_exact_canonical_name"],
            "private_review_file":str(path),
            "country_verified":False,"acquisitions_appended":0,
            "database_write":False,"outbound_sent":False,
            "execution_authority":"none",
        },sort_keys=True))
        return 0
    if args.source=="first_party_search":
        packet=build_first_party_discovery_review(
            targets=targets,max_entities=args.max_source,
        )
        packet["target_query_limit"]=args.max_targets
        packet["target_selection_complete"]=False
        location=save_private(packet)
        print(json.dumps({
            "status":"READ_ONLY_FIRST_PARTY_SEARCH_REVIEW_PREPARED",
            "source":"first_party_search","country_focus":"GB",
            "entity_candidates_available":packet["entity_candidates_available"],
            "entities_selected_for_search":packet["entities_selected_for_search"],
            "search_errors":packet["search_errors"],
            "search_candidates_before_cross_entity_filter":packet[
                "search_candidates_before_cross_entity_filter"],
            "shared_existing_host_count":packet["shared_existing_host_count"],
            "entities_skipped_by_search_selector":packet[
                "entities_skipped_by_search_selector"],
            "website_probes_attempted":packet["website_probes_attempted"],
            "verified_company_site_review_count":packet[
                "verified_company_site_review_count"],
            "private_review_file":str(location),
            "country_verified":False,"database_write":False,
            "acquisitions_appended":0,"outbound_sent":False,
            "execution_authority":"none",
        },sort_keys=True))
        return 0
    observations=[]
    page_counts=[]
    for page in range(args.source_page,args.source_page+args.page_count):
        sampled=source_observations(
            source=args.source,sector=args.sector,country=args.country,
            metro=args.metro,max_source=args.max_source,
            source_page=page,
        )
        page_counts.append({"page":page,"observations":len(sampled)})
        observations.extend(sampled)
    packet=build_review(
        targets=targets,observations=observations,
        source=args.source,sector=args.sector,country=args.country,
    )
    packet["source_page"]=args.source_page
    packet["source_page_count"]=args.page_count
    packet["per_page_observations"]=page_counts
    packet["target_query_limit"]=args.max_targets
    packet["source_observation_limit_per_page"]=args.max_source
    packet["source_observation_limit_total"]=args.max_source*args.page_count
    packet["target_selection_complete"]=False
    packet["source_selection_complete"]=False
    location=save_private(packet)
    print(json.dumps({
        "status":"READ_ONLY_SOURCE_MATCH_REVIEW_PREPARED",
        "source":args.source,"sector":args.sector,
        "country":args.country,
        "source_page":args.source_page,
        "source_page_count":args.page_count,
        "source_page_observation_counts":page_counts,
        "source_observation_limit_total":args.max_source*args.page_count,
        "unique_target_entities_examined":packet[
            "unique_target_entities_examined"
        ],
        "unique_target_prospects_examined":packet[
            "unique_target_prospects_examined"
        ],
        "target_entities_with_website_evidence":packet[
            "target_entities_with_website_evidence"
        ],
        "target_entities_with_phone_evidence":packet[
            "target_entities_with_phone_evidence"
        ],
        "target_entities_with_linked_prospect_phone":packet[
            "target_entities_with_linked_prospect_phone"
        ],
        "target_prospects_with_linked_phone":packet[
            "target_prospects_with_linked_phone"
        ],
        "source_observations_with_website":packet[
            "source_observations_with_website"
        ],
        "source_observations_with_phone":packet[
            "source_observations_with_phone"
        ],
        "name_variant_review_count":packet[
            "name_variant_review_count"
        ],
        "target_relationship_rows_examined":packet[
            "target_relationship_rows_examined"
        ],
        "source_observations_examined":packet[
            "source_observations_examined"
        ],
        "potential_matched_observations":packet[
            "potential_matched_observations"
        ],
        "strong_evidence_review_count":packet[
            "strong_evidence_review_count"
        ],
        "manual_review_count":packet["manual_review_count"],
        "private_review_file":str(location),
        "database_write":False,"acquisitions_appended":0,
        "outbound_sent":False,"execution_authority":"none",
    },sort_keys=True))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError,ValueError) as exc:
        # Credentials and candidate details must never leak through stderr.
        print("SOURCE_ACQUISITION_RESULT=BLOCKED reason="
              +type(exc).__name__,file=sys.stderr)
        raise SystemExit(3)
