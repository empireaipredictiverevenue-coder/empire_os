"""Original EmpireOS CA18567 private land-intelligence method preview."""
from __future__ import annotations
import argparse
from pathlib import Path
import json
from empire_os.tender_land_intelligence_demonstrator import write_private_demo

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,default=Path.cwd())
    ap.add_argument("--write-private",action="store_true")
    args=ap.parse_args()
    if not args.write_private:
        print(json.dumps({"status":"HELD_EXPLICIT_PRIVATE_PREVIEW_FLAG_REQUIRED","outbound_sent":False,"bid_authorized":False}))
        return 2
    report=write_private_demo(args.repo_root)
    print(json.dumps({
        "status":report["status"],
        "examples":len(report["published_examples"]),
        "investment_ready_sites":report["investment_ready_sites"],
        "bid_authorized":report["bid_authorized"],
        "outbound_sent":report["outbound_sent"],
        "db_writes":report["db_writes"],
        "output_html":str(args.repo_root/"runtime/acquisition_research/ca18567_land_intelligence_demo_latest.html"),
        "output_json":str(args.repo_root/"runtime/acquisition_research/ca18567_land_intelligence_demo_latest.json"),
    },sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
