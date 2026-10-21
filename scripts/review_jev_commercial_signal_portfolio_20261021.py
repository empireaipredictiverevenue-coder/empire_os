"""Reconcile existing EmpireOS signal inbox into a private-safe executive summary.

Original posts, names, contact details, links and hashed item identifiers are
never written to this Git-reviewed report. No Prospect/CRM mutation or outbound.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from empire_os.jev_commercial_signal_portfolio import review_existing_intent_signals

SOURCE=Path("/srv/empire_os/runtime/acquisition/signal_inbox.json")
MAX_SOURCE_BYTES=12_000_000
OUTPUT_NAME="JEV_COMMERCIAL_INTENT_EXECUTIVE_REVIEW_20261021.json"
ALLOWED_SOURCE_TYPES=("reddit_intent","linkedin_intent","permits_nyc","courtlistener")


def build_private_safe_summary(signal_data, *, provider=None, model_budget=0):
    baseline=[]
    for _ in range(20):
        start=perf_counter()
        expected=review_existing_intent_signals(signal_data)
        baseline.append((perf_counter()-start)*1000)
    result=review_existing_intent_signals(
        signal_data,provider=provider,model_call_budget=model_budget)
    if result["lane_counts"]!=expected["lane_counts"]:
        raise ValueError("canonical intent portfolio drift")
    classes=Counter(
        row.get("source")
        for row in signal_data.values()
        if isinstance(row,dict) and row.get("source") in ALLOWED_SOURCE_TYPES
    )
    model_rows=[row for row in result["items"]
                if row["shadow_status"]!="NOT_CALLED"]
    return {
        "schema_version":"empire.jev.commercial_intent_private_safe_review.v1",
        "status":"LIVE_ORIGINAL_SIGNAL_PORTFOLIO_SHADOW_REVIEW_ONLY",
        "mode":"OBSERVE",
        "source_root":"existing_canonical_signal_inbox",
        "original_signal_record_count":len(signal_data),
        "selected_source_counts":dict(sorted(classes.items())),
        "intent_signals_selected":result["signals_selected_for_review"],
        "eligible_unresolved_intent_signals":result["eligible_unresolved_signals"],
        "distinct_original_intent_events_reviewed":result["review_item_count"],
        "source_duplicates_collapsed":result["duplicate_source_refs_collapsed"],
        "deterministic_review_lane_counts":result["lane_counts"],
        "deterministic_portfolio_median_elapsed_ms_20_samples":round(median(baseline),3),
        "local_shadow_attempts":result["local_model_attempts"],
        "local_model_reported_latency_ms":[row.get("local_model_latency_ms")
                                            for row in model_rows if
                                            row.get("local_model_latency_ms") is not None],
        "local_shadow_status_counts":dict(sorted(Counter(
            row["shadow_status"] for row in model_rows
        ).items())),
        "unverified_identity_records_not_promoted":True,
        "permit_records_not_treated_as_buyers":True,
        "court_observations_not_treated_as_buyers":True,
        "model_cannot_override_canonical_intent_decisions":True,
        "manual_qualified_buyer_review_required":True,
        "human_capacity_review_required_before_outreach":True,
        "verified_buyer_enquiries":0,
        "canonical_prospects_created":0,
        "outreach_sent":0,"financial_actions":0,"db_writes":False,
        "external_paid_jev_api_called":False,
        "execution_authority":"none",
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.add_argument("--local-shadow",action="store_true")
    parser.add_argument("--max-shadow-calls",type=int,default=0)
    args=parser.parse_args()
    if args.local_shadow != (args.max_shadow_calls>0):
        raise ValueError("explicit local shadow and call budget must agree")
    repo=Path(__file__).resolve().parents[1]
    output=repo/"docs/commercial"/OUTPUT_NAME
    if (SOURCE.is_symlink() or not SOURCE.is_file()
        or not 0<SOURCE.stat().st_size<=MAX_SOURCE_BYTES
        or output.exists() or output.is_symlink()):
        raise ValueError("unsafe canonical signal input or existing receipt")
    rows=json.loads(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(rows,dict):
        raise ValueError("canonical signal inbox is not a dictionary")
    provider=None
    if args.local_shadow:
        from empire_os.laya_http_provider import LayaHttpTypedDecisionProvider
        provider=LayaHttpTypedDecisionProvider(
            base_url="http://127.0.0.1:8769",timeout_s=3)
    receipt=build_private_safe_summary(
        rows,provider=provider,model_budget=args.max_shadow_calls)
    receipt["generated_at_utc"]=datetime.now(timezone.utc).isoformat()
    with output.open("x",encoding="utf8") as out:
        json.dump(receipt,out,indent=2,sort_keys=True)
        out.write("\n")
    print(json.dumps({
        "status":receipt["status"],
        "intent_signals":receipt["intent_signals_selected"],
        "lanes":receipt["deterministic_review_lane_counts"],
        "model_calls":receipt["local_shadow_attempts"],
        "verified_buyers":receipt["verified_buyer_enquiries"],
        "outreach":receipt["outreach_sent"],
    },sort_keys=True))


if __name__=="__main__":
    main()
