"""Original CA18567 tender consultant offline document excerpt preview."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from empire_os.tender_supplier_rfq_review import AWAIT, READY, preview, write_private


def main() -> int:
    parser=argparse.ArgumentParser(
        description="Preview bounded local supplier document content, never authorise bids",
    )
    parser.add_argument("--repo-root",default="/srv/empire_os")
    parser.add_argument("--write-private",action="store_true")
    args=parser.parse_args()
    root=Path(args.repo_root)
    report=preview(root)
    saved=False
    if report["status"] in (AWAIT,READY) and args.write_private:
        try:
            write_private(root,report)
            saved=True
        except (ValueError,OSError):
            saved=False
    summary={key:value for key,value in report.items() if key!="documents"}
    summary["private_preview_written"]=saved
    print(json.dumps(summary,sort_keys=True))
    return 0 if report["status"] in (AWAIT,READY) and (
        not args.write_private or saved) else 2


if __name__=="__main__":
    raise SystemExit(main())
