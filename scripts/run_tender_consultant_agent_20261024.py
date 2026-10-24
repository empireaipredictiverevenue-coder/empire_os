"""On-demand EmpireOS Tender Consultant Agent. No new worker or systemd timer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.tender_consultant_agent import (
    READY, review, save_private, _base, local_shadow_advice,
)


def main() -> int:
    parser=argparse.ArgumentParser(
        description="Original EmpireOS procurement consultant research; never submits a bid",
    )
    parser.add_argument("--repo-root",default="/srv/empire_os")
    parser.add_argument("--write-private",action="store_true")
    parser.add_argument("--shadow-local",action="store_true",
                        help="Ask original loopback LLM for strictly unverified questions")
    args=parser.parse_args()
    result=review(Path(args.repo_root))
    if result["status"]==READY and args.shadow_local:
        result["local_shadow_questions"]=local_shadow_advice(result)
    saved=False
    if result["status"]==READY and args.write_private:
        try:
            save_private(Path(args.repo_root),result)
            saved=True
        except (OSError,ValueError):
            result=_base()
    overview={key:value for key,value in result.items() if key!="briefs"}
    overview.update({
        "private_consultation_saved":saved,
        "number_of_consultancy_briefs":len(result.get("briefs",[])),
        "total_human_actions":sum(len(x.get("consultant_owner_tasks",[]))
                                 for x in result.get("briefs",[])),
        "original_tender_system_preserved":True,
        "supplier_documents_status":result.get("ca18567_supplier_document_intake",{}).get("status","NOT_CHECKED"),
        "supplier_documents_observed":result.get("ca18567_supplier_document_intake",{}).get("documents_observed",0),
        "local_shadow_status":result.get("local_shadow_questions",{}).get("status","NOT_REQUESTED"),
    })
    print(json.dumps(overview,sort_keys=True))
    return 0 if result["status"]==READY else 2


if __name__=="__main__":
    raise SystemExit(main())
