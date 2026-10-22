"""Review historical prospect sectors against fresh Market GPS and Buyer Scout.

Reads existing bounded aggregate receipts only. Optional local model shadow
gets sector labels/counts, never people, contacts or original source text.
No DB connection, network except existing loopback Laya, dispatch or approval.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path

from empire_os.jev_sector_research_priority import prioritize_sector_research

PRODUCTION=Path("/srv/empire_os")
ARCHIVE=Path("docs/commercial/JEV_LARGE_PROSPECT_DUMP_STREAM_20261021.json")
ARCHIVE_SHA256="bb4cdee0cd2e2d4bd6a20f63b4721375981e701873c7f878ded4a27cfa5919ab"
GPS=Path("runtime/market_sweeps/revenue_gps_latest.json")
CAPACITY=Path("runtime/buyer_capacity_readiness/latest.json")
OUTPUT=Path("docs/commercial/JEV_SECTOR_RESEARCH_PRIORITY_20261022.json")


def _read_bounded(path:Path, max_bytes:int)->dict|None:
    try:
        if (path.is_symlink() or not path.is_file()
            or not 0<path.stat().st_size<=max_bytes):
            return None
        data=json.loads(path.read_text())
        return data if isinstance(data,dict) else None
    except (ValueError,TypeError,OSError,UnicodeError):
        return None


def run_sector_review(*,local_shadow:bool=False,max_shadow_calls:int=0)->dict:
    if (local_shadow != (max_shadow_calls>0)
        or type(max_shadow_calls) is not int
        or not 0<=max_shadow_calls<=2):
        raise ValueError("explicit bounded local shadow only")
    root=Path(__file__).resolve().parents[1]
    archive_path=root/ARCHIVE
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ValueError("historical source receipt unavailable")
    raw=archive_path.read_bytes()
    if sha256(raw).hexdigest()!=ARCHIVE_SHA256:
        raise ValueError("historical original source receipt changed")
    original=json.loads(raw)
    provider=None
    if local_shadow:
        from empire_os.laya_http_provider import LayaHttpTypedDecisionProvider
        provider=LayaHttpTypedDecisionProvider(
            base_url="http://127.0.0.1:8769",timeout_s=3)
    result=prioritize_sector_research(
        original,
        market_gps=_read_bounded(PRODUCTION/GPS,250000),
        buyer_capacity=_read_bounded(PRODUCTION/CAPACITY,100000),
        as_of=datetime.now(timezone.utc),
        provider=provider,max_shadow_calls=max_shadow_calls,
    )
    if (result["outreach_sent"]!=0 or result["database_writes"] is not False
        or result["verified_contactable_leads"]!=0
        or result["prospects_scored_individually"]!=0
        or result["execution_authority"]!="none"):
        raise ValueError("research status is not commercial execution")
    result["original_source_receipt_sha256"]=ARCHIVE_SHA256
    result["audit_time_utc"]=datetime.now(timezone.utc).isoformat()
    return result


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.add_argument("--local-shadow",action="store_true")
    parser.add_argument("--max-shadow-calls",type=int,default=0)
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    target=repo/OUTPUT
    if target.exists() or target.is_symlink() or not target.parent.is_dir():
        raise ValueError("refuse overwrite of reviewed sector priority packet")
    result=run_sector_review(
        local_shadow=args.local_shadow,
        max_shadow_calls=args.max_shadow_calls)
    with target.open("x",encoding="utf-8") as out:
        json.dump(result,out,sort_keys=True,indent=2)
        out.write("\n")
    print(json.dumps({
        "status":result["status"],
        "sector_count":result["sector_count"],
        "research_lanes":result["research_lane_counts"],
        "market_snapshot_current":result["market_gps_snapshot_current"],
        "buyer_capacity_status":result["buyer_capacity_source_status"],
        "local_shadow_attempts":result["local_shadow_attempts"],
        "verified_contactable_leads":result["verified_contactable_leads"],
        "outreach":result["outreach_sent"],
    },sort_keys=True))


if __name__=="__main__":
    main()
