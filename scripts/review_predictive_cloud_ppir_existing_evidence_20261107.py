"""Read-only PPIR evidence baseline for the EXISTING Search Fabric/Decodo product.

Precision/Intelligence/Revenue remain UNKNOWN without independent labels,
outcome verification and attributable costs. This is not another crawler/API.
Never outputs URLs, domains, contacts or secret values. No provider calls.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping

from urllib.parse import urlsplit
from empire_os.scrapling_source_evidence import _public_url, EvidenceSourceHold

DISCOVERY = Path("/srv/empire_os/runtime/search/decodo_service_business_discovery.json")
LEDGER = Path("/srv/empire_os/runtime/search/decodo_request_ledger.json")
DISCOVERY_SCHEMA = "empire.decodo.service_business_discovery.v1"
LEDGER_SCHEMA = "empire.search_fabric.decodo_request_ledger.v1"
MAX_ROWS = 80
MAX_AGE = timedelta(days=14)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class EvidenceHold(ValueError):
    pass


def _read(path: Path, max_bytes: int) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise EvidenceHold("private_source_missing_or_unsafe")
    info = path.stat()
    if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > max_bytes or info.st_size <= 0):
        raise EvidenceHold("private_source_ownership_or_size_untrusted")
    try:
        payload = json.loads(path.read_text(encoding="utf8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise EvidenceHold("source_parse_failure") from exc
    if not isinstance(payload, dict):
        raise EvidenceHold("source_document_not_object")
    return payload


def audit_evidence(
    discovery: Mapping[str, Any], ledger: Mapping[str, Any],
    *, now: datetime,
) -> dict[str, Any]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise EvidenceHold("audit_clock_not_timezone_aware")
    now = now.astimezone(timezone.utc)
    if (not isinstance(discovery, Mapping)
            or discovery.get("schema_version") != DISCOVERY_SCHEMA
            or discovery.get("source") != "decodo_web_data"):
        raise EvidenceHold("discovery_source_contract_mismatch")
    rows = discovery.get("entries")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise EvidenceHold("untrusted_candidate_count")
    seen: set[str] = set()
    fresh = 0
    stale = 0
    search_provenance = 0
    for row in rows:
        if not isinstance(row, Mapping):
            raise EvidenceHold("invalid_candidate_row")
        # Existing discovery is a RESEARCH artifact. Never accept self-attested
        # verified customer, approved outreach or stronger evidence claims.
        if (row.get("evidence_state") != "SEARCH_RESULT_REQUIRES_FIRST_PARTY_VERIFICATION"
                or row.get("qualified_customer") is not False
                or row.get("outreach_authorized") is not False):
            raise EvidenceHold("candidate_promotion_requires_independent_first_party_proof")
        host = row.get("domain")
        url = row.get("website")
        try:
            canonical_host = urlsplit(_public_url(url)).hostname
        except EvidenceSourceHold as exc:
            raise EvidenceHold("untrusted_candidate_website") from exc
        if (not isinstance(host, str) or canonical_host != host or host in seen):
            raise EvidenceHold("untrusted_duplicate_or_mismatched_domain")
        seen.add(host)
        query = row.get("source_query")
        if (row.get("source") != "decodo_web_data"
                or not isinstance(query, str) or not 1 <= len(query.strip()) <= 200
                or not isinstance(row.get("search_title_unverified"), str)):
            raise EvidenceHold("missing_search_source_provenance")
        try:
            observed = datetime.fromisoformat(row["observed_at"].replace("Z","+00:00"))
            if observed.tzinfo is None or observed.utcoffset() is None:
                raise ValueError("naive")
            age = now - observed.astimezone(timezone.utc)
        except (TypeError, KeyError, ValueError, AttributeError) as exc:
            raise EvidenceHold("invalid_source_timestamp") from exc
        if age < timedelta(0):
            raise EvidenceHold("future_dated_search_result")
        search_provenance += 1
        if age <= MAX_AGE:
            fresh += 1
        else:
            stale += 1
    if (not isinstance(ledger, Mapping)
            or ledger.get("schema_version") != LEDGER_SCHEMA
            or type(ledger.get("total_attempts")) is not int
            or ledger["total_attempts"] < 0
            or type(ledger.get("provider_hold")) is not bool
            or not isinstance(ledger.get("attempts_by_day"), dict)):
        raise EvidenceHold("provider_attempt_ledger_untrusted")
    window = ledger.get("billing_window")
    if (not isinstance(window, str) or not re.fullmatch(r"\d{4}-\d{2}",window)):
        raise EvidenceHold("ledger_window_invalid")
    try:
        datetime.strptime(window+"-01", "%Y-%m-%d")
    except ValueError as exc:
        raise EvidenceHold("ledger_window_invalid") from exc
    totals = ledger["attempts_by_day"]
    if any(not isinstance(k,str) or not DATE_RE.fullmatch(k)
           or type(n) is not int or n<0 or not k.startswith(window+"-")
           for k,n in totals.items()):
        raise EvidenceHold("ledger_daily_attempts_invalid")
    try:
        if any(datetime.strptime(k,"%Y-%m-%d").date().isoformat()!=k for k in totals):
            raise EvidenceHold("ledger_date_invalid")
    except ValueError as exc:
        raise EvidenceHold("ledger_date_invalid") from exc
    if sum(totals.values())!=ledger["total_attempts"]:
        raise EvidenceHold("provider_attempt_total_mismatch")
    # Discovery records have no transaction IDs linking them to provider
    # attempts. Never compute an acquisition "yield" from two separate ledgers.
    return {
        "schema_version":"empire.predictive_cloud.ppir_evidence_audit.v1",
        "mode":"READ_ONLY",
        "observed_at_utc":now.isoformat(),
        "precision":{
            "candidates_observed":len(rows),
            "unique_candidate_domains":len(seen),
            # Counts above describe unverified RAW search-result observations.
            # Admission must be reviewed by the original Search Fabric policy.
            # This independent audit intentionally does not duplicate that
            # owner policy or promote source results to eligible businesses.
            "raw_candidate_count_is_not_source_policy_admission":True,
            "source_policy_eligible_research_rows":None,
            "source_policy_rejected_research_rows":None,
            "source_policy_review_status":"NOT_ASSESSED_BY_PPIR_AUDIT",
            "fresh_search_result_candidates":fresh,
            "stale_search_result_candidates":stale,
            "search_provenance_present":search_provenance,
            "independently_verified_entity_count_in_this_artifact":0,
            "top_k_precision":None,
            "precision_status":"UNMEASURABLE_NO_LABELLED_FIRST_PARTY_TRUTH",
        },
        "power":{
            "provider_attempts_in_billing_window":ledger["total_attempts"],
            "billing_window":window,
            "provider_hold":ledger["provider_hold"],
            "successful_provider_calls":None,
            "requests_linked_to_verified_entities":None,
            "p95_latency_ms":None,
            "verified_cost_per_entity":None,
            "throughput_sustained_per_hour":None,
        },
        "intelligence":{
            "independently_scored_recommendations":None,
            "measured_predictive_uplift":None,
            "forecast_calibration":None,
            "status":"NO_LABELLED_OUTCOMES_OR_MATCHED_BASELINE",
        },
        "revenue":{
            "verified_attributable_revenue":None,
            "verified_gross_profit":None,
            "cost_per_qualified_opportunity":None,
            "paying_customers_from_this_artifact":None,
            "status":"NO_LINKED_CUSTOMER_OUTCOME_OR_SETTLED_COST",
        },
        "readiness":{
            "qualified_customer_claim_authorized":False,
            "external_data_delivery_authorized":False,
            "paid_provider_calls_made_by_audit":0,
            "production_changes":False,
            "benchmark_validated":False,
            "raw_discovery_results_are_not_customer_admission":True,
            "next_required_evidence":[
                "original_search_fabric_source_policy_admission_for_fixed_cohort",
                "first_party_identity_truth_labels_for_fixed_candidate_cohort",
                "per_request_provider_receipts_cost_and_latency_with_attribution",
                "paired_independent_intelligence_baseline_and_outcome_labels",
                "consented_customer_acceptance_and_realized_margin",
            ],
        },
    }


def run(discovery_path: Path=DISCOVERY, ledger_path: Path=LEDGER,
        *, now:datetime|None=None) -> dict[str,Any]:
    return audit_evidence(
        _read(discovery_path,100000),_read(ledger_path,8192),
        now=now or datetime.now(timezone.utc),
    )


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args()
    if not args.read_only:
        parser.error("explicit --read-only required")
    try:
        print(json.dumps(run(),sort_keys=True,indent=2))
    except EvidenceHold as exc:
        raise SystemExit(json.dumps({"status":"PPIR_EVIDENCE_HOLD","reason":str(exc)}))
