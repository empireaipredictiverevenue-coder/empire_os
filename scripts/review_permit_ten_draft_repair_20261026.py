"""Owner-facing read-only preview of exact 10 Workspace draft repairs.

Uses the original private Permit workbench, exact pinned ten drafts, original
authenticated Google Workspace provider and canonical founder postal footer.
The current token does NOT have gmail.compose; this tool never changes drafts.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from datetime import datetime,timezone

from empire_os.permit_workspace_ten_draft_repair_preflight import preview

ROOT=Path(__file__).resolve().parents[1]


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only",action="store_true",required=True)
    args=p.parse_args(argv)
    result=preview(root=ROOT,now=datetime.now(timezone.utc))
    print(json.dumps(result,sort_keys=True))
    if result.get("messages_sent") or result.get("gmail_draft_updates_performed"):
        raise ValueError("PERMIT_READONLY_REPAIR_PREVIEW_AUTHORITY_ESCALATED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
