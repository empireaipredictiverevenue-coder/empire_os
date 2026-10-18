"""Exact-statement evidence preflight before any intelligence product report.

This handles *internal* preflight ONLY; even supported statements cannot be
released, billed, emailed, distributed or presented as commercial verification.
No free-form sales copy is validated, and unknown products/claims fail closed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json,re

from empire_os.intelligence_data_products import get_data_product
from empire_os.property_claim_receipt_runtime import (
    PATH as CLAIMS_PATH,validated_claims,
)
from empire_os.property_claim_evidence_review import (
    _validated_full_day,
    REPORT_REL,
)

SCHEMA="empire.intelligence_product_claim_preflight.v1"
MAX_CLAIMS=12
SUPPORTED_BY_PRODUCT={
    "nyc_permit_project_verification":frozenset({
        "DOB_ISSUED_PERMIT_EVENT",
        "OTI_PLUTO_TAXLOT_REFERENCE_MATCH",
        "OTI_BBL_CONFLICT_RECORDED",
        "DOB_CO_BBL_REFERENCE_CORROBORATES_DOB_PERMIT",
        "DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS",
        "PLUTO_PUBLISHED_STORAGE_AREA_VALUE",
    }),
    "property_intelligence_monitor":frozenset({
        "DOB_ISSUED_PERMIT_EVENT",
        "OTI_PLUTO_TAXLOT_REFERENCE_MATCH",
        "OTI_BBL_CONFLICT_RECORDED",
        "DOB_CO_BBL_REFERENCE_CORROBORATES_DOB_PERMIT",
        "DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS",
        "PLUTO_PUBLISHED_STORAGE_AREA_VALUE",
    }),
    "permit_intelligence_feed":frozenset({
        "DOB_ISSUED_PERMIT_EVENT",
        "DOB_CO_BBL_REFERENCE_CORROBORATES_DOB_PERMIT",
    }),
}
SRC_FOR_KIND={
    "DOB_ISSUED_PERMIT_EVENT":("rbx6-tga4",),
    "OTI_PLUTO_TAXLOT_REFERENCE_MATCH":("5zhs-2jue","64uk-42ks"),
    "OTI_BBL_CONFLICT_RECORDED":("rbx6-tga4","5zhs-2jue"),
    "DOB_CO_BBL_REFERENCE_CORROBORATES_DOB_PERMIT":("pkdm-hqz6",),
    "DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS":("64uk-42ks",),
    "PLUTO_PUBLISHED_STORAGE_AREA_VALUE":("64uk-42ks",),
}
BIN=re.compile(r"[1-5]\d{6}\Z")
BBL=re.compile(r"\d{10}\Z")
RECEIPT_SHA=re.compile(r"[a-f0-9]{64}\Z")


def _is_product(key:str)->bool:
    return key in SUPPORTED_BY_PRODUCT or get_data_product(key) is not None


def _source_chain(root:Path,now:datetime)->dict|None:
    """Hash-bind the private claim artifact to the *current* full-day report."""
    packet=validated_claims(root,now=now)
    if packet is None:return None
    try:
        report, digest=_validated_full_day(root/REPORT_REL)
        if (digest!=packet.get("source_full_day_report_sha256")
                or report.get("issued_day")!=packet.get("source_full_day_issued_date")):
            return None
        return packet
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError):
        return None


def _template(kind:str,item:Mapping[str,Any])->str:
    refs=item["entity_reference"]
    b=refs["bin"];lot=refs["dob_bbl"]
    c=item.get("source_dof_building_class_as_reported")
    desc=item.get("source_dof_building_class_label")
    if kind=="DOB_ISSUED_PERMIT_EVENT":
        return (f"Official NYC DOB NOW records an issued permit event for BIN {b} "
                f"and published BBL {lot} (issued-day observation only).")
    if kind=="OTI_PLUTO_TAXLOT_REFERENCE_MATCH":
        return (f"Official NYC OTI building BIN {b} has a published PLUTO lot "
                f"reference matching BBL {lot}; property ownership and current use unverified.")
    if kind=="OTI_BBL_CONFLICT_RECORDED":
        return (f"DOB lists BBL {lot} for BIN {b}, whereas the OTI building "
                f"footprint refers to a different lot; discrepancy unresolved.")
    if kind=="DOB_CO_BBL_REFERENCE_CORROBORATES_DOB_PERMIT":
        return (f"Selected NYC DOB NOW Certificate of Occupancy records match "
                f"BIN {b} and BBL {lot}; OTI lot discrepancy remains unresolved.")
    if kind=="DOF_PUBLISHED_WAREHOUSE_BUILDING_CLASS":
        return (f"NYC PLUTO records class {c} ({desc}) for lot BBL {lot} "
                f"associated with BIN {b}; warehouse operation is not verified.")
    if kind=="PLUTO_PUBLISHED_STORAGE_AREA_VALUE":
        return (f"NYC PLUTO records storage-area field value "
                f"{item['source_pluto_storage_area_as_reported']} for BBL {lot}; "
                f"this is a source field, not a verified on-site measurement.")
    raise ValueError("UNSUPPORTED_CLAIM_KIND")


def review_data_product_claims(
    *, product_key:str, requested_claims:list[Mapping[str,Any]],
    repo_root:Path, now:datetime|None=None,
) -> dict[str,Any]:
    """Return exact source-rendered internal preview, never a customer release.

    Callers cannot supply their own prose, provenance, rights flags, source IDs
    or authority. Supported wording is rendered from locally checked evidence.
    Any unsupported claim denies the entire requested report.
    """
    clock=now or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("NAIVE_CLAIM_OBSERVATION_TIME")
    clock=clock.astimezone(timezone.utc)
    base={
        "schema_version":SCHEMA,
        "product_key":str(product_key) if isinstance(product_key,str) else "",
        "mode":"OBSERVE",
        "status":"HOLD_NO_EVIDENCE_BOUND_REPORT",
        "evidence_status":"NOT_VERIFIED_FOR_DELIVERY",
        "internal_preview_authorized":False,
        "customer_distribution_authorized":False,
        "external_data_export_authorized":False,
        "outbound_authorized":False,
        "payment_or_invoice_authorized":False,
        "verified_revenue":False,
        "execution_authority":"none",
        "validated_claims":[],
        "claim_count":0,
    }
    if (not isinstance(product_key,str) or not _is_product(product_key)
            or not isinstance(requested_claims,list)
            or not 1<=len(requested_claims)<=MAX_CLAIMS
            or any(not isinstance(q,Mapping) for q in requested_claims)):
        return {**base,"reason_code":"UNSUPPORTED_PRODUCT_OR_CLAIMS"}
    allowed=SUPPORTED_BY_PRODUCT.get(product_key)
    if not allowed:
        return {**base,"reason_code":"PRODUCT_NOT_CLAIM_MAPPED"}
    query=[]
    seen=set()
    for candidate in requested_claims:
        # Exact DTO allowlist: rejects caller-written marketing text or
        # attempts to smuggle approval or customer data into the preview.
        if set(candidate)!={"statement_id","bin","dob_bbl"}:
            return {**base,"reason_code":"UNAPPROVED_CLAIM_FIELDS"}
        kind=candidate.get("statement_id")
        bin_id=candidate.get("bin")
        lot=candidate.get("dob_bbl")
        if (not isinstance(kind,str) or kind not in allowed or
                not isinstance(bin_id,str) or not BIN.fullmatch(bin_id) or
                not isinstance(lot,str) or not BBL.fullmatch(lot)):
            return {**base,"reason_code":"UNSUPPORTED_STATEMENT_OR_REFERENCE"}
        key=(kind,bin_id,lot)
        if key in seen:
            return {**base,"reason_code":"DUPLICATE_ASSERTION"}
        seen.add(key)
        query.append(key)
    root=Path(repo_root).resolve()
    evidence=_source_chain(root,clock)
    if evidence is None:
        return {**base,"reason_code":"MISSING_STALE_OR_MISMATCHED_SOURCE_RECEIPTS"}
    by_ref={(c["entity_reference"]["bin"],c["entity_reference"]["dob_bbl"]):c
            for c in evidence["claim_reviews"]}
    found=[]
    for kind,bin_id,lot in query:
        packet=by_ref.get((bin_id,lot))
        if packet is None or kind not in packet["allowed_evidence_statements"]:
            return {**base,"reason_code":"STATEMENT_NOT_SUPPORTED_BY_OFFICIAL_SOURCES"}
        sources=SRC_FOR_KIND[kind]
        receipts=packet["evidence_receipts"]
        ids={r["source_dataset_id"] for r in receipts}
        if any(source not in ids for source in sources):
            return {**base,"reason_code":"REQUIRED_SOURCE_RECEIPT_MISSING"}
        text=_template(kind,packet)
        source_evidence=[]
        packet_receipts={r["source_dataset_id"]:r
                         for r in packet["evidence_receipts"]}
        for source in sources:
            receipt=packet_receipts[source]
            selected_digest=(receipt.get("local_full_day_report_sha256")
                             if source=="rbx6-tga4" else
                             receipt.get("selected_source_response_sha256"))
            if (not isinstance(selected_digest,str)
                    or not RECEIPT_SHA.fullmatch(selected_digest)):
                return {**base,"reason_code":"MISSING_SOURCE_RESPONSE_DIGEST"}
            source_evidence.append({
                "official_dataset_id":source,
                "official_dataset_page":
                    "https://data.cityofnewyork.us/d/"+source,
                "local_selected_source_digest":selected_digest,
                "digest_is_publisher_signature":False,
                "observation_scoped_not_business_identity":True,
            })
        found.append({
            "statement_id":kind,
            "bin":bin_id,"dob_bbl":lot,
            "source_scoped_statement_text":text,
            "official_source_dataset_ids":list(sources),
            "source_evidence_receipts":source_evidence,
            "source_observed_at_utc":evidence["observed_at_utc"],
            "evidence_grade":packet["evidence_grade"],
            "full_day_report_sha256":evidence["source_full_day_report_sha256"],
            "not_proven":packet["not_proven"],
            "external_customer_release_authorized":False,
        })
    digest=sha256(json.dumps(found,sort_keys=True,ensure_ascii=True,
                             separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {
        **base,
        "status":"PRIVATE_SOURCE_BOUND_CLAIM_PREVIEW_ONLY",
        "evidence_status":"OFFICIAL_SELECTED_SOURCE_CLAIM_SCOPE_VALIDATED",
        "internal_preview_authorized":True,
        "claim_count":len(found),
        "validated_claims":found,
        "internal_preview_sha256":digest,
        "digest_is_external_attestation":False,
        "rights_review_still_required":True,
        "reason_code":"SOURCE_SUPPORT_NOT_COMMERCIAL_RELEASE",
    }



def source_bound_catalog_summary(repo_root:Path,*,now:datetime|None=None)->dict[str,Any]:
    """Only aggregate statuses; not itself a customer claim or licence."""
    at=now or datetime.now(timezone.utc)
    source=_source_chain(Path(repo_root).resolve(),at)
    base={
        "status":"NO_CURRENT_VERIFIED_CLAIM_RECEIPT",
        "reference_pair_count":None,
        "warehouse_class_reference_pair_count":None,
        "operating_businesses_verified":0,
        "customer_claim_delivery_authorized":False,
        "source_specific_licence_approved":False,
    }
    if source is None:
        return base
    groups=source.get("claim_reviews")
    if not isinstance(groups,list) or len(groups)!=4:
        return base
    warehouse=sum(c.get("evidence_grade")==
                  "THREE_AGENCY_REFERENCE_PLUS_DOF_WAREHOUSE_CLASS"
                  for c in groups)
    if warehouse!=2:
        return base
    return {**base,
        "status":"FOUR_SOURCE_BOUND_REFERENCE_CLAIMS_FOR_INTERNAL_REVIEW",
        "reference_pair_count":4,
        "warehouse_class_reference_pair_count":2,
    }
