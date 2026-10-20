"""EmpireOS cross-owner release board — read-only git/source overlap inventory.

Coordinates releases; does not claim ownership of source owners, merge code,
stage changes, deploy their services, read customer records, or execute agents.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

SCHEMA="empire.integration.cross_agent_release_board.v1"
OWNER_WORKTREES=(
    ("predictive_decision","/home/ubuntu/empire_agents/predictive_decision_control_20261018"),
    ("a2a_signal_miner","/home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020"),
    ("lead_supply","/home/ubuntu/empire_worktrees/lead_supply_intelligence_20261019"),
    ("agency_acquisition","/home/ubuntu/empire_worktrees/agency_acquisition_conversion_20261020"),
    ("agency_reply","/home/ubuntu/empire_worktrees/agency_reply_first_video_20261020"),
    ("buyer_response","/home/ubuntu/empire_worktrees/buyer_fast_response_review_20261019"),
    ("buyer_triage","/home/ubuntu/empire_worktrees/buyer25_founder_commercial_triage_20261019"),
    ("buyer_commercial","/home/ubuntu/empire_worktrees/commercial_buyer_decision_20261019"),
    ("finance_foundation","/home/ubuntu/empire_worktrees/empire_finance_os_foundation_20261020"),
    ("finance_custody","/home/ubuntu/empire_worktrees/enterprise_finance_custody_20261018"),
    ("revenue_fabric","/home/ubuntu/empire_worktrees/lead_revenue_fabric_unified_20261019"),
    ("revenue_attribution","/home/ubuntu/empire_worktrees/revenue_causal_attribution_v2_20261019"),
    ("data_brokerage","/home/ubuntu/empire_worktrees/data_brokerage_monetization_20261018"),
    ("marketing_solar","/home/ubuntu/empire_worktrees/marketing_solar_payer_gates_20261020"),
    ("local_market","/home/ubuntu/empire_worktrees/local_revenue_intelligence_20261019"),
    ("crm_predictive","/home/ubuntu/empire_worktrees/crm_predictive_autonomy_integrated_20261018"),
    ("crm_sales","/home/ubuntu/empire_worktrees/crm_predictive_sales_readiness_20261018"),
    ("revenue_source","/home/ubuntu/empire_worktrees/predictive_revenue_source_contract_20261018"),
    ("storm_product","/home/ubuntu/empire_agents/completion_wave3/storm-product"),
    ("cloud_analytics","/home/ubuntu/empire_agents/completion_wave2/cloud-analytics"),
)
OWNER_REQUIREMENTS={
    "predictive_decision":"PROSPECTIVE_PROFIT_REGISTRY_AND_FINANCE_CUSTODY",
    "a2a_signal_miner":"SOURCE_OWNER_EVIDENCE_AND_TENANT_A2A_SIGNATURE",
    "lead_supply":"ORIGINAL_CONSENTED_ZIP_INVENTORY_AND_BUYER_ACCEPTANCE",
    "agency_acquisition":"AUTHENTICATED_CUSTOMER_REPLY_AND_SOURCE_REVIEW",
    "agency_reply":"CANONICAL_SENT_THREAD_AND_ORIGINAL_BUYER_ROLE",
    "buyer_response":"PROVIDER_THREAD_AUTHENTICATION_AND_SINGLE_WRITER",
    "buyer_triage":"BUYER_ROLE_TERMS_CAPACITY_AND_NO_DUPLICATE_CONTACT",
    "buyer_commercial":"BUYING_CAPACITY_APPROVED_TERMS_AND_FINANCE",
    "finance_foundation":"FINANCE_READER_GRANTS_AND_PAID_EVENT_CUSTODY",
    "finance_custody":"ACTUAL_PAYMENT_REFUNDS_INVOICES_CASH_RECONCILIATION",
    "revenue_fabric":"ORIGINAL_SOURCE_EVENTS_AND_IDEMPOTENT_TENANT_JOIN",
    "revenue_attribution":"PROSPECTIVE_COHORT_AND_AUTHENTICATED_OUTCOMES",
    "data_brokerage":"LICENSING_ORIGINAL_BUYER_CONTRACT_AND_SALE",
    "marketing_solar":"PRICING_PAYER_ELIGIBILITY_AND_SPEND_APPROVAL",
    "local_market":"TERRITORY_GEO_SOURCE_EPOCH_AND_CAPACITY",
    "crm_predictive":"CRM_OWNER_SINGLE_WRITER_AND_SOURCE_REVISIONS",
    "crm_sales":"CRM_LEAD_TERMS_AND_BUYER_AUTHORIZATION",
    "revenue_source":"RESTRICTED_CANONICAL_READS_AND_SCHEMA_CONSISTENCY",
    "storm_product":"STORM_SOURCE_FRESHNESS_AND_SERVICEABILITY",
    "cloud_analytics":"SOURCE_CUSTODY_SHADOW_VS_LIVE_OPTIMIZATION",
}


def _git(folder:Path,*args:str,cap:int=1_000_000)->str:
    p=subprocess.run(
        ["git","-C",str(folder),*args],text=True,
        capture_output=True,timeout=15,check=False,
    )
    if p.returncode:
        raise ValueError("git read-only inspection unavailable: "+args[0])
    if len(p.stdout)>cap:
        raise ValueError("git output exceeds bounded release inventory")
    return p.stdout.strip()


def review_board(production:str="/srv/empire_os")->dict:
    prod=Path(production).resolve()
    prod_head=_git(prod,"rev-parse","HEAD")
    prod_branch=_git(prod,"branch","--show-current")
    prod_status=_git(prod,"status","--porcelain",cap=5_000_000).splitlines()
    prod_dirty=set()
    for item in prod_status:
        # Git porcelain v1 may include paths with spaces; no PII is output.
        if len(item)>=4:
            prod_dirty.add(item[3:].split(" -> ")[-1])
    blocks=[]
    for role,location in OWNER_WORKTREES:
        root=Path(location)
        if not root.is_dir():
            blocks.append({
                "owner":role,"state":"OWNER_WORKTREE_MISSING",
                "next_proof":OWNER_REQUIREMENTS[role],
            })
            continue
        try:
            head=_git(root,"rev-parse","HEAD")
            branch=_git(root,"branch","--show-current")
            ancestor=_git(prod,"merge-base",prod_head,head)
            edits=_git(prod,"diff","--name-only",ancestor,head,cap=4_000_000)
            changed=set(edits.splitlines()) if edits else set()
            dirty=_git(root,"status","--porcelain",cap=3_000_000).splitlines()
            overlaps=sorted(changed&prod_dirty)
            # The board reports only overlap counts, not a misleading
            # content-level merge feasibility certification.
            state=(
                "SAME_COMMIT_AS_PRODUCTION" if head==prod_head else
                "OWNER_DIRTY_REQUIRES_COORDINATION" if dirty else
                "PRODUCTION_PATH_COLLISIONS_REQUIRE_REVIEW" if overlaps else
                "CANDIDATE_DIFF_REVIEW_REQUIRED"
            )
            blocks.append({
                "owner":role,"state":state,"commit":head,
                "branch":branch or "(detached)",
                "owner_uncommitted_change_rows":len(dirty),
                "committed_changed_file_count_since_common_ancestor":len(changed),
                "production_uncommitted_file_path_collision_count":len(overlaps),
                "direct_merge_authorized":False,
                "source_semantics_reconciled":False,
                "next_proof":OWNER_REQUIREMENTS[role],
            })
        except (OSError,ValueError,subprocess.TimeoutExpired):
            blocks.append({
                "owner":role,"state":"GIT_EVIDENCE_UNAVAILABLE_HOLD",
                "direct_merge_authorized":False,
                "next_proof":OWNER_REQUIREMENTS[role],
            })
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"CROSS_AGENT_RELEASE_BOARD_REVIEWED_NO_MERGE",
        "observed_at":datetime.now(timezone.utc).isoformat(),
        "production_head":prod_head,"production_branch":prod_branch,
        "production_dirty_change_rows":len(prod_status),
        "priority_owner_count":len(OWNER_WORKTREES),
        "owner_reviews":blocks,
        "read_only_predictive_release_is_full_prod_merge":False,
        "owner_dependencies_independently_satisfied":False,
        "all_agent_work_automatically_promoted":False,
        "merges_executed":False,"deployments_performed":False,
        "services_restarted":False,"database_writes":False,
        "execution_authority":"none",
    }


def main()->int:
    cli=argparse.ArgumentParser()
    cli.add_argument("--read-only",action="store_true",required=True)
    cli.add_argument("--production-root",default="/srv/empire_os")
    args=cli.parse_args()
    print(json.dumps(review_board(args.production_root),sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
