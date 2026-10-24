"""Original CA18567 consultant private supplier-document evidence desk."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.tender_supplier_evidence_intake import (
    HELD, DROP, ensure_private_drop, inventory, save_private,
)


def main() -> int:
    parser=argparse.ArgumentParser(
        description="Private supplier-document custody only; no issuer/supplier approval",
    )
    parser.add_argument("--repo-root",default="/srv/empire_os")
    parser.add_argument("--prepare-private-drop",action="store_true")
    parser.add_argument("--write-private",action="store_true")
    args=parser.parse_args()
    root=Path(args.repo_root).resolve(strict=True)
    try:
        if args.prepare_private_drop:
            ensure_private_drop(root)
        report=inventory(root)
        saved=False
        if args.write_private and report["status"]!=HELD:
            save_private(root,report)
            saved=True
    except (OSError,ValueError):
        report=inventory(root)
        saved=False
    summary={k:v for k,v in report.items() if k not in (
        "documents","required_supplier_and_rfq_evidence",
    )}
    summary["private_receipt_written"]=saved
    summary["private_drop_path"]=str(root/DROP)
    print(json.dumps(summary,sort_keys=True))
    return 2 if report["status"]==HELD else 0


if __name__=="__main__":
    raise SystemExit(main())
