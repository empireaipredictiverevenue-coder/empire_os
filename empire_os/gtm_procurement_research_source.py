"""Read-only public procurement research for the original GTM observer.

A public RFP proves an external notice exists; it does not prove a customer
of Empire AI, buyer response consent, deliverability or contact authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit
import json
import os
import stat

REPORT = Path("runtime/acquisition_research/official_procurement_requirements_latest.json")
SCHEMA = "empire.acquisition_official_procurement_review.v1"
HOLDS = frozenset({
    "CUSTOM_SCOPE_NO_VERIFIED_PRODUCT_FIT",
    "NO_PAID_TRAFFIC_POLICY_HOLD",
    "DIGITAL_MARKETING_PAID_SCOPE_NOT_EXCLUDED_HOLD",
    "SERVICE_SCOPE_NEEDS_INDEPENDENT_FIT_REVIEW",
    "CATALOG_PRODUCT_NOT_READY",
    "PRODUCT_HYPOTHESIS_REQUIRES_SCOPE_REVIEW",
})


def assess_procurement(packet: Mapping[str, Any] | None, *, now: datetime) -> dict[str, Any]:
    held = {
        "status": "OFFICIAL_PROCUREMENT_RESEARCH_RECEIPT_REQUIRED",
        "current_research_receipt": False,
        "official_releases_inspected": None,
        "public_service_requests_observed": None,
        "product_fit_hypotheses_only": None,
        "verified_empire_ai_buyers": 0,
        "contact_authorized": False,
        "crm_writes": False,
        "outbound_authorized": False,
        "execution_authority": "none",
    }
    if not isinstance(packet, Mapping) or now.tzinfo is None:
        return held
    if (packet.get("schema_version") != SCHEMA
        or packet.get("mode") != "OBSERVE"
        or packet.get("outbound_authorized") is not False
        or packet.get("crm_writes") is not False
        or packet.get("model_training_authorized") is not False
        or packet.get("verified_revenue") is not None
        or packet.get("canonical_qualified") != 0
        or packet.get("external_bid_submitted") is not False
        or packet.get("verified_customer_inquiry") is not False):
        return held
    try:
        stamp=datetime.fromisoformat(str(packet["observed_at"]).replace("Z","+00:00"))
        if (stamp.utcoffset() is None or not timedelta(0) <=
            now.astimezone(timezone.utc)-stamp.astimezone(timezone.utc) <= timedelta(hours=24)):
            return held
    except (KeyError, ValueError, TypeError):
        return held
    records=packet.get("records")
    inspected=packet.get("releases_inspected")
    count=packet.get("open_service_requirements_identified")
    hypotheses=packet.get("product_hypotheses")
    if (not isinstance(records,list)
        or any(type(n) is not int for n in (inspected,count,hypotheses))
        or not 0 <= count <= inspected <= 600
        or not 0 <= hypotheses <= count or len(records) != count):
        return held
    for item in records:
        if (not isinstance(item, Mapping)
            or item.get("review_status") not in HOLDS
            or item.get("outbound_authorized") is not False
            or item.get("contact_permission_cleared") is not False
            or item.get("buyer_interest_in_empire_ai_verified") is not False
            or item.get("product_fit_verified") is not False):
            return held
        url=item.get("notice_url")
        parts=urlsplit(url if isinstance(url,str) else "")
        if (parts.scheme != "https" or parts.hostname not in (
            "www.find-tender.service.gov.uk",
            "www.contractsfinder.service.gov.uk")):
            return held
    if sum(x.get("candidate_product_code") is not None for x in records) != hypotheses:
        return held
    return {
        **held,
        "status": "PUBLIC_PROCUREMENT_RESEARCH_ONLY_NO_CONTACT_AUTHORITY",
        "current_research_receipt": True,
        "official_releases_inspected": inspected,
        "public_service_requests_observed": count,
        "product_fit_hypotheses_only": hypotheses,
    }


def observe_procurement(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    clock=now or datetime.now(timezone.utc)
    path=root / REPORT
    try:
        if path.is_symlink() or (root / REPORT.parent).is_symlink():
            raise ValueError("symlinked receipt")
        st=path.stat()
        if (not stat.S_ISREG(st.st_mode)
            or st.st_uid not in (os.geteuid(), 0)
            or st.st_mode & 0o077
            or not 0 < st.st_size <= 200_000):
            raise ValueError("untrusted research receipt")
        packet=json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        packet=None
    return assess_procurement(packet,now=clock)


def summarize_acquisition_truth(
    owner_ops: Mapping[str, Any],
    owner_sales: Mapping[str, Any],
    procurement: Mapping[str, Any],
) -> dict[str, Any]:
    """Two non-interchangeable lanes: authenticated sales count vs public RFPs."""
    source_valid=owner_ops.get("source_count_verified") is True
    total=owner_ops.get("canonical_sales_acquisitions") if source_valid else None
    if type(total) is not int or total < 0:
        source_valid=False
        total=None
    if total is None:
        status="FIRST_PARTY_OWNER_COUNT_UNVERIFIED"
    elif total==0:
        status="FIRST_PARTY_NO_RECORDED_SALES_ENQUIRIES"
    else:
        status="FIRST_PARTY_SALES_ENQUIRY_REQUIRES_EXACT_RECEIPT_REVIEW"
    return {
        "schema_version":"empire.gtm.acquisition_owner_truth.v1",
        "mode":"OBSERVE",
        "status":status,
        "canonical_first_party_counts_owner_verified":source_valid,
        "canonical_first_party_sales_acquisitions":total,
        "crm_owner_reconciliation_status":owner_sales.get("status"),
        "exact_customer_lineage_verified":False,
        "specific_current_response_consent_verified":False,
        "procurement_research":procurement,
        "public_procurement_not_counted_as_first_party":True,
        "contact_review_ready":False,
        "copy_briefs_generated":0,
        "outbound_authorized":False,
        "crm_writes":False,
        "payment_activation":False,
        "verified_revenue":None,
        "execution_authority":"none",
    }
