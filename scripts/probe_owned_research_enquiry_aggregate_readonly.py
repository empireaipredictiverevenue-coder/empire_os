#!/usr/bin/env python3
"""Existing EmpireDB: founder-owned research interest, COUNT-ONLY observer.

This is a one-hit local read-only operator, not a CRM migration, campaign
analytics service, or outreach authorization. The research intake is separate
from the consented Commercial/Predictive sales source; do not sum it as sales.

Database access follows the already-installed canonical read-only founder
source operator pattern. Never print credentials, emails, names, enquiry text,
receipt UUIDs, campaign IDs, event IDs or per-campaign metrics.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from typing import Any, Callable

SCHEMA = "empire.seo.owned_research_enquiry_aggregate_readonly.v1"
SQL = r"""
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '7000ms';
SET LOCAL lock_timeout = '2000ms';
WITH enquiries AS MATERIALIZED (
  SELECT count(*) AS total,
         count(DISTINCT campaign_id) AS campaign_count,
         count(*) FILTER (WHERE marketing_consent IS NOT FALSE
                             OR outbound_authorized IS NOT FALSE
                             OR automatic_followup IS NOT FALSE) AS violated_holds
  FROM public.owned_campaign_enquiries
), events AS MATERIALIZED (
  SELECT count(*) FILTER (WHERE event_type = 'campaign_enquiry_submitted'
                            AND evidence_class = 'server_received_enquiry'
                            AND enquiry_receipt IS NOT NULL) AS submitted,
         count(*) FILTER (WHERE event_type = 'campaign_page_view'
                            AND evidence_class = 'browser_observation') AS page_views,
         count(*) FILTER (WHERE event_type = 'campaign_cta_click'
                            AND evidence_class = 'browser_observation') AS cta_clicks,
         count(*) FILTER (WHERE event_type = 'campaign_enquiry_started'
                            AND evidence_class = 'browser_observation') AS starts,
         count(*) FILTER (WHERE event_type = 'campaign_enquiry_submitted'
                            AND (evidence_class <> 'server_received_enquiry'
                              OR enquiry_receipt IS NULL)) AS invalid_submission_events
  FROM public.owned_campaign_events
)
SELECT jsonb_build_object(
 'research_enquiry_rows', e.total,
 'research_campaigns_with_enquiries', e.campaign_count,
 'enquiry_marketing_or_outbound_hold_violations', e.violated_holds,
 'server_received_submission_events', x.submitted,
 'browser_page_view_events', x.page_views,
 'browser_cta_click_events', x.cta_clicks,
 'browser_enquiry_started_events', x.starts,
 'invalid_submission_events', x.invalid_submission_events
)::text
FROM enquiries e CROSS JOIN events x;
ROLLBACK;
"""
FIELDS = (
    "research_enquiry_rows",
    "research_campaigns_with_enquiries",
    "enquiry_marketing_or_outbound_hold_violations",
    "server_received_submission_events",
    "browser_page_view_events",
    "browser_cta_click_events",
    "browser_enquiry_started_events",
    "invalid_submission_events",
)


def classify(*, privileged: bool, returncode: int, stdout: str) -> dict[str, Any]:
    result:dict[str,Any] = {
        "schema_version": SCHEMA,
        "status": "HELD_UNVERIFIED_EVIDENCE",
        "mode": "OBSERVE",
        "source": "CANONICAL_EMPIREDB",
        "read_only": True,
        "queries_bounded_to_aggregate_counts": True,
        "raw_customer_rows_read_by_operator": False,
        "customer_identifiers_disclosed": False,
        "contact_data_disclosed": False,
        "individual_enquiry_text_disclosed": False,
        "campaign_identifiers_disclosed": False,
        "commercial_sales_status_inferred": False,
        "lead_transfer_enabled": False,
        "outbound_sent": False,
        "database_writes": False,
        "new_privileges_granted": False,
        "payment_executed": False,
        "execution_authority": "NONE",
    }
    if not privileged:
        result["reason_code"] = "AUTHORIZED_LOCAL_READONLY_OPERATOR_REQUIRED"
        return result
    if returncode != 0:
        result["reason_code"] = "OWNED_RESEARCH_AGGREGATE_UNAVAILABLE"
        return result
    try:
        if len(stdout) > 8192:
            raise ValueError("oversized query output")
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        if len(lines) != 1 or not lines[0].startswith("{"):
            raise ValueError("unexpected aggregate response")
        packet = json.loads(lines[0])
        if (not isinstance(packet,dict) or set(packet) != set(FIELDS)
            or any(type(packet[k]) is not int or not 0 <= packet[k] <= 1_000_000_000 for k in FIELDS)):
            raise ValueError("untrusted aggregate fields")
        if (packet["research_campaigns_with_enquiries"] > packet["research_enquiry_rows"]
            or packet["enquiry_marketing_or_outbound_hold_violations"] > packet["research_enquiry_rows"]):
            raise ValueError("contradictory research counts")
    except (ValueError, TypeError, KeyError):
        result["reason_code"] = "UNTRUSTED_RESEARCH_AGGREGATE_RESPONSE"
        return result
    result.update(packet)
    matches = (
        packet["research_enquiry_rows"] == packet["server_received_submission_events"]
        and packet["enquiry_marketing_or_outbound_hold_violations"] == 0
        and packet["invalid_submission_events"] == 0
    )
    result["aggregate_event_consistency_verified"] = matches
    if not matches:
        result["status"] = "RESEARCH_ENQUIRY_EVIDENCE_INCONSISTENT_REVIEW_REQUIRED"
        result["next_action"] = "REVIEW_AGGREGATE_RECEIPT_PROVENANCE_PRIVATELY"
    elif packet["research_enquiry_rows"] == 0:
        result["status"] = "NO_RESEARCH_ENQUIRIES_IN_CANONICAL_SOURCE"
        result["next_action"] = "WAIT_FOR_GENUINE_USER_INITIATED_RESEARCH_ENQUIRY"
    else:
        result["status"] = "RESEARCH_ENQUIRIES_OBSERVED_SEPARATE_FROM_SALES"
        result["next_action"] = "REVIEW_CONSENT_AND_COMMERCIAL_FIT_BEFORE_PROMOTION"
    return result


def run(*, euid:int|None=None, command_runner:Callable[...,Any]|None=None) -> dict[str,Any]:
    uid = os.geteuid() if euid is None else euid
    if uid != 0:
        return classify(privileged=False,returncode=2,stdout="")
    argv = [
        "/usr/sbin/runuser", "-u", "postgres", "--",
        "/usr/bin/psql", "-X", "-q", "-w", "-A", "-t",
        "-v", "ON_ERROR_STOP=1", "-h", "/var/run/postgresql",
        "-d", "empiredb", "-f", "-",
    ]
    try:
        completed = (command_runner or subprocess.run)(
            argv,input=SQL,text=True,capture_output=True,timeout=13,
            check=False,env={"PATH":"/usr/bin:/bin","LC_ALL":"C",
                             "PGCONNECT_TIMEOUT":"4"},
        )
    except (OSError,subprocess.TimeoutExpired,ValueError):
        return classify(privileged=True,returncode=1,stdout="")
    return classify(privileged=True,returncode=completed.returncode,
                    stdout=completed.stdout)


def main() -> int:
    parser=argparse.ArgumentParser(description="Founder-owned bounded research enquiry aggregate observation")
    parser.add_argument("--review-only",action="store_true",required=True)
    args=parser.parse_args()
    print(json.dumps(run(),sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
