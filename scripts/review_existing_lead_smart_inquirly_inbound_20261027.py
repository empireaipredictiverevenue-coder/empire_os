"""Read-only classification of existing Lead Smart and inquirly inbound replies.

Uses the canonical existing buyer-relationship registry and original Lead Smart
commercial pulse. No Gmail login, no extra CRM, no writes, no route activation.
Gmail original message text must be reviewed independently when it changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
from typing import Any

REGISTRY = Path(
    "/srv/empire_os/runtime/buyer_network_intelligence/"
    "commercial_relationship_registry_latest.json"
)
PULSE = Path("/srv/empire_os/runtime/revenue/lead_smart/commercial_pulse/latest.json")

def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size < 1_000_000:
        raise ValueError("CANONICAL_SOURCE_UNAVAILABLE")
    data=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(data,dict):
        raise ValueError("CANONICAL_SOURCE_INVALID")
    return data

def _dt(value: Any) -> datetime:
    if not isinstance(value,str):
        raise ValueError("SOURCE_TIME_MISSING")
    clock=datetime.fromisoformat(value.replace("Z","+00:00"))
    if clock.tzinfo is None:
        raise ValueError("SOURCE_TIME_NOT_AWARE")
    return clock.astimezone(timezone.utc)

def review(registry: dict, pulse: dict, *, now: datetime) -> dict:
    if now.tzinfo is None: raise ValueError("AWARE_CLOCK_REQUIRED")
    current=now.astimezone(timezone.utc)
    if (registry.get("schema_version")!="empire.commercial_relationship_registry.v1"
        or registry.get("mode")!="OBSERVE"
        or registry.get("execution_authority")!="NONE"
        or not isinstance(registry.get("relationships"),list)
        or len(registry["relationships"])>500
        or pulse.get("schema_version")!="empire.lead_smart.commercial_pulse.v1"
        or pulse.get("buyer")!="Lead Smart"
        or pulse.get("campaign_id")!="CA8278ed3f26e9495b881fe3833174d007"):
        raise ValueError("WRONG_OR_UNTRUSTED_CANONICAL_SOURCE")

    rows={}
    for x in registry["relationships"]:
        if not isinstance(x,dict):
            raise ValueError("INVALID_SOURCE_ROW")
        if x.get("entity_key") not in ("lead-smart","inquirly.com"):continue
        if x["entity_key"] in rows:raise ValueError("DUPLICATE_PARTNER_ROW")
        rows[x["entity_key"]]=x
    if set(rows)!={"lead-smart","inquirly.com"}:
        raise ValueError("TWO_EXACT_PARTNER_ROWS_REQUIRED")
    lead,inq=rows["lead-smart"],rows["inquirly.com"]
    if (
        lead.get("last_inbound_message_id")!="1a16911d65d0b41b"
        or lead.get("next_founder_action")!="REVIEW_EXISTING_ROUTING_RECORDING_REPLY_NO_REPEAT"
        or lead.get("commercial_buyer_approved") is not False
        or inq.get("last_inbound_message_id")!="1a14540463907582"
        or inq.get("next_founder_action")!="DEFER_INQUIRLY_UNTIL_VERIFIED_TRAFFIC_NO_REPEAT_REQUEST"
        or inq.get("reviewed_buyer_reply_disposition",{}).get("status")!="PARTNER_REPORTS_NO_PILOT_WITHOUT_ESTABLISHED_TRAFFIC"
        or lead.get("outbound_authorized") is not False
        or inq.get("outbound_authorized") is not False
        or lead.get("partner_commercial_terms_verified") is True
        or inq.get("partner_commercial_terms_verified") is True
    ):
        raise ValueError("CANONICAL_PARTNER_DISPOSITION_CHANGED_REVIEW_AGAIN")
    for r in (lead,inq):
        if _dt(r.get("last_inbound_at"))>current:
            raise ValueError("FUTURE_PROVIDER_MESSAGE")
    ended=_dt(pulse.get("campaign_expires_at"))
    if (pulse.get("site_handoff_switch_enabled") is not False
        or type(pulse.get("site_handoffs_recorded")) is not int
        or pulse["site_handoffs_recorded"] != 0
        or pulse.get("qualified_billable_calls_verified") is not False
        or pulse.get("settled_revenue_verified") is not False):
        raise ValueError("LIVE_CALL_OR_PAYMENT_STATE_CHANGED_REVIEW_AGAIN")
    if ended>current:
        raise ValueError("PILOT_NOT_YET_EXPIRED_RECHECK_STATUS")
    return {
        "schema_version":"empire.earned_media.two_partner_inbound_review.v1",
        "mode":"READ_ONLY",
        "status":"INBOUND_REQUIREMENTS_CLASSIFIED_NO_NEW_OUTBOUND",
        "source_registry_generated_at":registry.get("generated_at"),
        "lead_smart": {
            "provider_last_reply_at":lead["last_inbound_at"],
            "provider_last_reply_message_ref":"gmail:1a16911d65d0b41b",
            "source_state":"EXISTING_REPLY_REVIEWED_NOT_NEW_BUYER_ACCEPTANCE",
            "answered_in_original_thread":[
                "DID route previously test-approved by partner",
                "RTB is bid/duration pre-check option, not proof mandatory DID migration",
                "Call qualification varies by buyer: 60-150 total seconds, not fixed 120 connected seconds",
                "Nonrelevant, spam, solicitation, renter, coached/incentivized calls can be unpaid",
                "Ringba displayed bid is not confirmed payout; provider and buyer scrubs/disputes apply",
                "Provider reporting is in original Ringba Reporting tab",
                "Offer hours depend on caller timezone and buyers can pause intraday",
                "ACH, wire and PayPal were described as payment options"
            ],
            "present_site_handoffs":0,
            "previous_supervised_pilot_expired_at":pulse["campaign_expires_at"],
            "site_call_admission_enabled":False,
            "original_routing_or_full_requirements_request_repeat":False,
            "next_existing_owner_action":"KEEP_CALL_ADMISSION_OFF_AND_RECONCILE_EXISTING_RINGBA_REPORTING; REQUIRE_FRESH_SUPERVISED_SCOPE_BEFORE_NEW_TRAFFIC",
            "not_verified":[
                "actual originating homeowner to accepted buyer connection",
                "buyer final acceptance/disposition and adjustments per call ID",
                "final payable amount and verified settlement",
                "fresh supervised pilot authority after expired window"
            ],
            "verified_accepted_payable_calls":0,
            "terms_fully_accepted":False
        },
        "inquirly": {
            "provider_last_reply_at":inq["last_inbound_at"],
            "provider_last_reply_message_ref":"gmail:1a14540463907582",
            "source_state":"PILOT_ELIGIBILITY_ANSWERED_PARTNER_DECLINED_NEW_UNPROVEN_TRAFFIC_SOURCE",
            "decision":"DEFER_EXISTING_INQUIRLY_APPLICATION_UNTIL_VERIFIED_FIRST_PARTY_TRAFFIC",
            "current_pilot_available":False,
            "repeat_original_requirements_request":False,
            "reactivation_condition":"INDEPENDENT_SOURCE_AND_ORGANIC_TRAFFIC_EVIDENCE_AND_PARTNER_REOPENING",
            "confirmed_roofing_buybox":False,
            "terms_fully_accepted":False
        },
        "canonical_crm_write_performed":False,
        "recorded_commercial_terms":False,
        "buyer_contract_accepted":False,
        "website_changed":False,
        "astra_release_modified":False,
        "email_sent":False,
        "payment_requested":False,
        "revenue_recognized":False,
    }

def main(argv: list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",required=True,action="store_true")
    a=parser.parse_args(argv)
    try:
        out=review(_load(REGISTRY),_load(PULSE),now=datetime.now(timezone.utc))
        print(json.dumps(out,sort_keys=True))
        return 0
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as e:
        print(json.dumps({
            "status":"HOLD_REVIEW_CURRENT_CANONICAL_EVIDENCE",
            "reason_code":str(e)[:100],
            "execution_authority":"none",
            "outbound_sent":False,
            "crm_writes":False
        },sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
