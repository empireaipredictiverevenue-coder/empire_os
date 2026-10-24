"""Private CA18567 land GIS evidence runner, within original tender lane.

No GIS point is invented. Real candidate screening needs an explicitly staged,
reviewed-by-founder input geometry; publication and bid status stay off.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import os
import stat
from empire_os.tender_land_gis_evidence import (
    snapshot_official_layers, screen_unverified_parcel_geometry,
)

INPUT = "ca18567_candidate_geometry_for_review.json"


def _read_private_input(root: Path) -> dict:
    folder = root.resolve(strict=True) / "runtime/acquisition_research"
    st = folder.lstat()
    if folder.is_symlink() or not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode)!=0o700 or st.st_uid!=os.geteuid():
        raise ValueError("PRIVATE_SOURCE_FOLDER_REQUIRED")
    f = folder / INPUT
    if f.is_symlink():
        raise ValueError("SYMLINK_INPUT_REFUSED")
    with f.open("rb") as fp:
        st=os.fstat(fp.fileno())
        if (not stat.S_ISREG(st.st_mode) or st.st_size>20000 or st.st_size<30
            or st.st_uid!=os.geteuid() or stat.S_IMODE(st.st_mode)!=0o600):
            raise ValueError("SOURCE_INPUT_PERMISSIONS_OR_SIZE_INVALID")
        doc=json.load(fp)
    if not isinstance(doc,dict) or set(doc) != {"reference","jurisdiction","geometry","geometry_source"}:
        raise ValueError("EXPECTED_UNVERIFIED_GEOMETRY_FIELDS")
    return doc


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo-root",default="/srv/empire_os")
    parser.add_argument("--write-private",action="store_true")
    parser.add_argument("--official-snapshot",action="store_true")
    parser.add_argument("--screen-staged-polygon",action="store_true")
    args=parser.parse_args()
    if not args.write_private or args.official_snapshot == args.screen_staged_polygon:
        print(json.dumps({"status":"HELD_EXPLICIT_EXACTLY_ONE_PRIVATE_GIS_OPERATION","bid_authorized":False}))
        return 2
    root=Path(args.repo_root)
    if args.official_snapshot:
        result=snapshot_official_layers(root)
        print(json.dumps({
            "status":result["status"],
            "layers_observed":result["layer_count"],
            "features_per_layer":{x["source_id"]:x["feature_count"] for x in result["layers"]},
            "full_parcel_screening":False,
            "bid_authorized":False,
        },sort_keys=True))
        return 0 if result["layer_count"]==2 else 2
    source=_read_private_input(root)
    result=screen_unverified_parcel_geometry(root,**source)
    print(json.dumps({
        "status":result["status"],"candidate_reference":result["candidate_reference"],
        "layer":result["source_catalogue"],
        "potential_intersections":len(result["intersections"]),
        "parcel_boundary_legally_verified":False,
        "bid_authorized":False,
    },sort_keys=True))
    return 0 if result["status"] in (
        "GIS_INTERSECTION_RESULT_NOT_LAND_OR_PLANNING_CLEARANCE",
        "POTENTIAL_SPATIAL_CONFLICTS_PARTIAL_RESULT_HUMAN_REVIEW",
    ) else 2

if __name__=="__main__":
    raise SystemExit(main())
