#!/usr/bin/env python3
"""Read-only preflight for a manually prepared commercial email.

Input: JSON via stdin {"subject":...,"body":...,"evidence_ref":...}.
Never sends, looks up a recipient, writes an event, or grants Gmail access.
"""
from __future__ import annotations
import argparse
import json
import sys
from empire_os.rapport_value_final_boundary import review_manual_email_draft


def main(argv=None,*,input_stream=None,output_stream=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    parsed=parser.parse_args(argv)
    out=output_stream or sys.stdout
    if not parsed.read_only:
        print(json.dumps({"status":"HOLD_READ_ONLY_REQUIRED",
                          "send_authority":"none"}),file=out)
        return 2
    try:
        raw=(input_stream or sys.stdin).read(12001)
        if len(raw)>12000:
            raise ValueError("BOUNDED_MANUAL_DRAFT_REQUIRED")
        doc=json.loads(raw)
        if type(doc) is not dict or set(doc)!={"subject","body","evidence_ref"}:
            raise ValueError("EXACT_DRAFT_REVIEW_CONTRACT_REQUIRED")
        result=review_manual_email_draft(
            subject=doc["subject"],body=doc["body"],
            evidence_ref=doc["evidence_ref"],
        )
    except (ValueError,TypeError,UnicodeError,KeyError):
        print(json.dumps({"status":"HOLD_MANUAL_DRAFT_INVALID",
                          "send_authority":"none"}),file=out)
        return 2
    print(json.dumps({
        "status":("VALUE_ONLY_DRAFT_CONTENT_REVIEW_PASSED"
                  if result["approved_for_cold_content_review"]
                  else "HOLD_PREMATURE_COMMERCIAL_DRAFT"),
        "blockers":result["blockers"],
        "policy":result["policy"],
        "verified_buyer_reply_authenticated":False,
        "commercial_cta_allowed":False,
        "send_authority":"none",
        "external_gmail_send_intercepted":False,
    },sort_keys=True),file=out)
    return 0 if result["approved_for_cold_content_review"] else 1


if __name__=="__main__":
    raise SystemExit(main())
