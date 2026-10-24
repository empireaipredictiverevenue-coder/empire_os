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
    parser.add_argument("--review-supplier-content",action="store_true",
                        help="Privately preview staged CA18567 DOCX text; PDFs remain unextracted")
    parser.add_argument("--land-intelligence-demo",action="store_true",
                        help="Generate CA18567 source-linked private research demonstrator; no investment clearance")
    parser.add_argument("--official-gis-snapshot",action="store_true",
                        help="Fetch bounded official NI/ROI GIS samples into private research; no site qualification")
    parser.add_argument("--commercial-readiness",action="store_true",
                        help="Private CA18567 sent-receipt/RFQ/illustrative-economics gate; no bid authority")
    args=parser.parse_args()
    result=review(Path(args.repo_root))
    if result["status"]==READY and args.review_supplier_content:
        from empire_os.tender_supplier_rfq_review import (
            AWAIT as RFQ_AWAIT, READY as RFQ_READY, preview, write_private,
        )
        review_result=preview(Path(args.repo_root))
        preview_saved=False
        if args.write_private and review_result["status"] in (RFQ_AWAIT,RFQ_READY):
            try:
                write_private(Path(args.repo_root),review_result)
                preview_saved=True
            except (OSError,ValueError):
                preview_saved=False
        # Only status/counts are added to the founder dossier. Untrusted
        # supplier text never enters the AI prompt, CRM or stdout.
        result["supplier_content_review"]={
            "status":review_result["status"],
            "docx_preview_count":review_result.get("docx_preview_count",0),
            "pdf_pending_extraction_count":review_result.get("pdf_pending_extraction_count",0),
            "private_preview_saved":preview_saved,
            "supplier_eligibility_verified":False,
            "scoring_subcriteria_verified":False,
            "rfq_fully_reviewed":False,
            "bid_authorized":False,
        }
    if result["status"]==READY and args.shadow_local:
        result["local_shadow_questions"]=local_shadow_advice(result)
    if result["status"]==READY and args.commercial_readiness:
        commercial_status="HELD_PRIVATE_WRITE_REQUIRED"
        sent_count=0
        if args.write_private:
            try:
                from empire_os.tender_commercial_readiness_20261024 import assess,save_private as save_commercial
                commercial=assess(Path(args.repo_root))
                save_commercial(Path(args.repo_root),commercial)
                commercial_status=commercial["status"]
                sent_count=commercial["approved_emails_sent_provider_count"]
            except (OSError,ValueError):
                commercial_status="HELD_UNSAFE_OR_MISSING_PRIVATE_COMMERCIAL_EVIDENCE"
        result["ca18567_commercial_readiness"]={
            "status":commercial_status,
            "provider_confirmed_sent_count":sent_count,
            "supplier_replies_at_original_send_receipt":0,
            "current_partner_reply_count":None,
            "live_gmail_checked_by_commercial_gate":False,
            "supplier_quotes_independently_verified":0,
            "authenticated_rfq_verified":False,
            "bid_authorized":False,
        }
    if result["status"]==READY and args.official_gis_snapshot:
        gis_status="HELD_PRIVATE_WRITE_REQUIRED"
        gis_layers_observed=0
        if args.write_private:
            try:
                from empire_os.tender_land_gis_evidence import snapshot_official_layers
                gis=snapshot_official_layers(Path(args.repo_root))
                gis_status=gis["status"]
                gis_layers_observed=gis["layer_count"]
            except (OSError,ValueError):
                gis_status="HELD_OFFICIAL_GIS_SNAPSHOT"
        result["official_gis_snapshot"]={
            "status":gis_status,
            "source_layers_observed":gis_layers_observed,
            "site_geometry_legally_verified":False,
            "planning_clearance_granted":False,
            "bid_authorized":False,
        }
    if result["status"]==READY and args.land_intelligence_demo:
        demo_status="HELD_PRIVATE_WRITE_REQUIRED"
        example_count=0
        if args.write_private:
            try:
                from empire_os.tender_land_intelligence_demonstrator import write_private_demo
                demo=write_private_demo(Path(args.repo_root))
                demo_status=demo["status"]
                example_count=len(demo["published_examples"])
            except (OSError,ValueError):
                demo_status="HELD_PRIVATE_LAND_DEMO_WRITE"
        result["land_intelligence_demo"]={
            "status":demo_status,
            "published_examples":example_count,
            "investment_ready_sites":0,
            "professional_review_verified":False,
            "supplier_eligibility_verified":False,
            "rfq_fully_reviewed":False,
            "bid_authorized":False,
        }
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
        "supplier_content_review_status":result.get("supplier_content_review",{}).get("status","NOT_REQUESTED"),
        "local_shadow_status":result.get("local_shadow_questions",{}).get("status","NOT_REQUESTED"),
    })
    print(json.dumps(overview,sort_keys=True))
    return 0 if result["status"]==READY else 2


if __name__=="__main__":
    raise SystemExit(main())
