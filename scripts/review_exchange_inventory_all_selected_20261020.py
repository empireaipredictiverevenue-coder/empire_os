"""Review EVERY bounded canonical Exchange selection row, no CRM/outreach writes.

Only original prospect UUID/reference, blocker, niche and corridor enter
owner-private local queue. Public stdout is a redacted aggregate. This is
not independent identity, consumer consent or buyer capacity verification.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from tempfile import mkstemp

from empire_os.exchange_inventory_owner_triage_v1 import (
    review_exchange_inventory_for_owner,redacted_founder_summary,
)

INPUT=Path("/srv/empire_os/runtime/commercial_exchange/latest.json")
OUT=Path(__file__).resolve().parents[1]/"runtime/exchange_inventory_review/owner_176_review_latest.json"


def _write_owner_file(path:Path,rows:dict)->None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("unsafe_private_owner_output")
    if path.parent.is_symlink():
        raise ValueError("unsafe_private_owner_directory")
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(path.parent,0o700)
    handle,temp=mkstemp(prefix=".owner_exchange_triage_",dir=path.parent)
    try:
        os.fchmod(handle,0o600)
        with os.fdopen(handle,"w",encoding="utf-8") as f:
            json.dump(rows,f,sort_keys=True,indent=2)
            f.write("\n")
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.add_argument("--snapshot",type=Path,default=INPUT)
    parser.add_argument("--write-owner-local",action="store_true")
    parser.add_argument("--owner-output",type=Path,default=OUT)
    args=parser.parse_args()
    try:
        f=args.snapshot
        if not f.is_file() or f.is_symlink() or f.stat().st_size>3_000_000:
            raise ValueError("snapshot_missing_oversized_or_symlink")
        data=json.loads(f.read_text(encoding="utf-8"))
        result=review_exchange_inventory_for_owner(data)
        if result.get("source_rows_fully_triaged") and args.write_owner_local:
            _write_owner_file(args.owner_output,result)
        print(json.dumps(redacted_founder_summary(result),sort_keys=True))
        return 0 if result.get("source_rows_fully_triaged") else 2
    except (ValueError,TypeError,OSError,UnicodeError,json.JSONDecodeError):
        # Do not echo a file path, identifier or source contents.
        print(json.dumps({
            "schema_version":"empire.exchange.inventory_owner_triage.v1",
            "state":"HOLD","reason":"source_unreadable_or_untrusted",
            "source_rows_fully_triaged":False,
            "crm_writes":False,"revenue_verified_cents":0,
        },sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
