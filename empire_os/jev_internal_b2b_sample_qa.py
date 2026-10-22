"""Small deterministic business-website QA canary for Jev pre-offer work.

Only the fixture-based workflow is activated here. No real person records,
source scraping, lead delivery, contact enrichment or buyer approval.
Website-listing omissions do not establish the absence of a website.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping
import re

SCHEMA="empire.jev.internal_b2b_website_qa.v1"
INPUT="empire.jev.internal_b2b_website_fixture.v1"
MAX_ROWS=25
CLASSIFICATIONS=frozenset((
    "REVIEWED_SITE_PROBLEM","LISTING_MISSING_SITE_FIELD",
    "REVIEWED_SITE_VALID","UNCERTAIN",
))
DOMAIN=re.compile(r"^[a-z0-9][a-z0-9-]{1,50}\.example$")
SAFE_KEY=re.compile(r"^SYN-[A-Z0-9]{2,12}$")


def review_internal_business_sample(
    fixture:Mapping[str,Any], *, expected_full_batch_size:int=50,
    stated_base_payment_usd:int=150,
)->dict[str,Any]:
    if (type(expected_full_batch_size) is not int or expected_full_batch_size!=50
        or type(stated_base_payment_usd) is not int or stated_base_payment_usd!=150):
        raise ValueError("unverified buyer terms cannot be altered")
    if (not isinstance(fixture,Mapping)
        or fixture.get("schema_version")!=INPUT
        or fixture.get("mode")!="SYNTHETIC_TEST_ONLY"
        or fixture.get("real_business_count")!=0
        or fixture.get("contact_details_included") is not False
        or fixture.get("source_licensing_of_real_records_verified") is not False
        or fixture.get("commercial_send_authorized") is not False):
        raise ValueError("only fictional business-only test data permitted")
    rows=fixture.get("rows")
    if not isinstance(rows,list) or not 1<=len(rows)<=MAX_ROWS:
        raise ValueError("synthetic test batch not bounded")
    identities=set()
    distinct_domains=set()
    dispositions=[]
    for row in rows:
        if not isinstance(row,Mapping):
            raise ValueError("synthetic case is not a business record")
        identifier=row.get("fixture_key")
        domain=row.get("fictional_domain")
        if (not isinstance(identifier,str) or SAFE_KEY.fullmatch(identifier) is None
            or identifier in identities
            or not isinstance(domain,str) or DOMAIN.fullmatch(domain) is None
            or row.get("company_is_fictional") is not True
            or row.get("personal_contact_included") is not False
            or row.get("business_only") is not True):
            raise ValueError("untrusted fixture or contact details")
        identities.add(identifier)
        first=row.get("reviewer_one_classification")
        second=row.get("reviewer_two_classification")
        if first not in CLASSIFICATIONS or second not in CLASSIFICATIONS:
            raise ValueError("unrecognized website review status")
        if any(type(row.get(k)) is not bool for k in (
            "source_review_complete","mock_reuse_rights_pass",
            "fictional_business_identity_matched","mock_primary_site_examined")):
            raise ValueError("unverified source workflow evidence")

        # De-dupe BEFORE qualification, including source rights checks. A
        # duplicate of a rejected record remains a duplicate, not a free
        # second try for a paid record.
        if domain in distinct_domains:
            lane="DUPLICATE_DOMAIN"
        elif not row["mock_reuse_rights_pass"]:
            lane="SOURCE_RIGHTS_HOLD"
        elif not row["source_review_complete"]:
            lane="ORIGINAL_SOURCE_REVIEW_HOLD"
        elif not row["fictional_business_identity_matched"]:
            lane="BUSINESS_IDENTITY_HOLD"
        elif first!=second:
            lane="REVIEWER_DISAGREEMENT_HOLD"
        elif first=="LISTING_MISSING_SITE_FIELD":
            lane="LISTING_OMISSION_NOT_WEBSITE_ABSENCE"
        elif first=="REVIEWED_SITE_VALID":
            lane="VALID_WEBSITE_NOT_A_NEED_SIGNAL"
        elif first=="UNCERTAIN":
            lane="INCONCLUSIVE_WEBSITE_STATUS"
        elif not row["mock_primary_site_examined"]:
            lane="PRIMARY_SITE_EXAMINATION_REQUIRED"
        else:
            lane="SYNTHETIC_QA_PATTERN_MATCH_ONLY"
        distinct_domains.add(domain)
        dispositions.append({
            "fixture_key":identifier,
            "qa_lane":lane,
            "synthetic_workflow_pattern_pass":lane=="SYNTHETIC_QA_PATTERN_MATCH_ONLY",
            "actual_company_verified":False,
            "actual_website_verified":False,
            "live_data_licence_verified":False,
            "actual_lead_accepted_by_buyer":False,
            "contact_or_delivery_permitted":False,
        })
    counts=Counter(x["qa_lane"] for x in dispositions)
    return {
        "schema_version":SCHEMA,
        "status":"SYNTHETIC_INTERNAL_QA_CANARY_NOT_ACTUAL_SUPPLY",
        "mode":"OBSERVE",
        "synthetic_records_checked":len(dispositions),
        "synthetic_distinct_domains":len(distinct_domains),
        "synthetic_qa_pattern_passes":counts["SYNTHETIC_QA_PATTERN_MATCH_ONLY"],
        "synthetic_lane_counts":dict(sorted(counts.items())),
        "fictional_qa_decisions":dispositions,
        "requested_full_batch_size":expected_full_batch_size,
        "conditional_gross_full_batch_usd":stated_base_payment_usd,
        "conditional_average_gross_per_accepted_if_all_fifty_accepted_usd":3,
        "partial_batch_payment_terms_confirmed":False,
        "actual_business_records_evaluated":0,
        "actual_verified_no_website_or_outdated_website_leads":0,
        "actual_available_accepted_records":0,
        "independent_source_licence_and_contact_rights_proven":False,
        "current_buyers_or_paid_orders_verified":0,
        "commercial_offer_ready":False,
        "customer_delivery_authorized":False,
        "outbound_sent":0,
        "database_writes":False,
        "execution_authority":"none",
    }
