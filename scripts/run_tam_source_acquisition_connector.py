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
    parser.add_argument("--source",choices=("recc_solar","overpass_osm"),
                        required=True)
    parser.add_argument("--sector",choices=("solar","roofing"),required=True)
    parser.add_argument("--country",choices=("GB","US"),required=True)
    parser.add_argument("--metro")
    parser.add_argument("--max-targets",type=int,default=250)
    parser.add_argument("--max-source",type=int,default=40)
    args=parser.parse_args(argv)
    validate_scope(source=args.source,sector=args.sector,
                   country=args.country,limit=args.max_targets)
    if not 1 <= args.max_source <= MAX_SOURCE:
        parser.error("source observation limit out of bounds")
    if os.geteuid()!=0:
        raise SystemExit("source acquisition connector requires authorised root")
    env=load_runtime_env("/etc/empiredb.env",required=("EMPIREDB_DSN",))
    targets=canonical_targets(env["EMPIREDB_DSN"],
                              sector=args.sector,limit=args.max_targets)
    observations=source_observations(
        source=args.source,sector=args.sector,country=args.country,
        metro=args.metro,max_source=args.max_source,
    )
    packet=build_review(
        targets=targets,observations=observations,
        source=args.source,sector=args.sector,country=args.country,
    )
    packet["target_query_limit"]=args.max_targets
    packet["source_observation_limit"]=args.max_source
    packet["target_selection_complete"]=False
    packet["source_selection_complete"]=False
    location=save_private(packet)
    print(json.dumps({
        "status":"READ_ONLY_SOURCE_MATCH_REVIEW_PREPARED",
        "source":args.source,"sector":args.sector,
        "country":args.country,
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
