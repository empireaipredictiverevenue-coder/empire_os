"""V19 independently reviewable release evidence register; NO approvals.

Builds only from V18's canonical rights docket. It is a structured
human-review work queue, not a permission / licence decision or
customer-distribution interface. No new DB tables, roles, timers, writes.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from empire_os.data_exchange_observation_custody import CustodyIntegrityError
from empire_os.data_exchange_rights_preflight import (
    PLANNING_FIELDS, REVIEWER_CHECKS, EXCLUDED_FIELDS,
)

SCHEMA="empire.data_exchange.release_evidence_register.v19"
REQUIREMENTS={
    "source_terms":(
        "Capture dated official dataset terms and OGL text, applicable exceptions",
        "Independently verify licence applies to the actual selected source fields",
    ),
    "field_scope":(
        "Document the seven exact persisted/derived fields and original API keys",
        "Verify third-party rights and copyright exceptions per field and local publisher",
    ),
    "privacy":(
        "Inspect all full transient JSON response keys and data types, without logging personal data",
        "Prove only the strict allowlisted projection enters custody; document raw-response disposal and log policy",
    ),
    "attribution":(
        "Review the proposed Crown/OGL notice and independent-service disclaimer",
        "Demonstrate link and attribution on each intended customer delivery surface before release",
    ),
    "provenance":(
        "Reconcile canonical observation SHA256 with source record IDs and retrieval date",
        "Independently establish source revision/publication dates; Empire fetch time is not publication date",
    ),
    "retention":(
        "Approve provenance-aware corrections, append-only superseding records and suppression policy",
        "Document retention, privacy-rights escalation, downstream withdrawal and erasure handling",
    ),
    "commercial_claims":(
        "Evidence which claims are supported by actual source revisions and real commercial outcomes",
        "Explicitly reject invented construction starts, buyers, property owners and prediction accuracy",
    ),
    "release_authority":(
        "File a dated independent review with scope, exceptions and accountable reviewer",
        "Record separate explicit founder release approval AFTER all evidence gates, not here",
    ),
}
RISK_CLASSES={
    "source_terms":"PUBLISHER_LICENCE",
    "field_scope":"THIRD_PARTY_RIGHTS",
    "privacy":"DATA_MINIMISATION",
    "attribution":"SOURCE_ACKNOWLEDGEMENT",
    "provenance":"DATA_AUTHENTICITY",
    "retention":"CORRECTION_AND_ERASURE",
    "commercial_claims":"MISREPRESENTATION",
    "release_authority":"FOUNDER_GOVERNANCE",
}


def build_release_evidence_register(docket: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(docket, Mapping):
        raise CustodyIntegrityError("canonical rights docket missing")
    if (
        docket.get("schema_version")!="empire.data_exchange.canonical_field_rights_docket.v18"
        or docket.get("status")!="REVIEW_DOCKET_READY_NOT_LICENSE_APPROVAL"
        or docket.get("source_field_rights_cleared") is not False
        or docket.get("customer_delivery_enabled") is not False
        or docket.get("data_resale_authorized") is not False
        or docket.get("production_writes") is not False
    ):
        raise CustodyIntegrityError("rights docket contains unreviewed authority")
    fields=docket.get("field_evidence_docket")
    checklist=docket.get("review_checklist")
    preview=docket.get("proposed_attribution_preview")
    if (
        not isinstance(fields,list)
        or len(fields)!=len(PLANNING_FIELDS)
        or {f.get("product_field") for f in fields if isinstance(f,dict)}
           != set(PLANNING_FIELDS)
        or any(not isinstance(f,dict)
               or f.get("origin_class")!=PLANNING_FIELDS[f["product_field"]]
               or f.get("client_distribution_authorised") is not False
               or f.get("independent_field_rights_review")!="NOT_COMPLETED"
               for f in fields)
        or not isinstance(checklist,list)
        or len(checklist)!=len(REVIEWER_CHECKS)
        or {c.get("control_id") for c in checklist if isinstance(c,dict)}
           != set(REQUIREMENTS)
        or any(not isinstance(c,dict)
               or c.get("signoff_artifact_present") is not False
               or c.get("verification_status")!="PENDING_HUMAN_AND_LEGAL_EVIDENCE_REVIEW"
               for c in checklist)
        or not isinstance(preview,Mapping)
        or preview.get("displayed_on_customer_product") is not False
        or preview.get("attribution_review_completed") is not False
        or preview.get("commercial_distribution_authorized") is not False
    ):
        raise CustodyIntegrityError("review controls not canonical / release authority forged")
    if (
        docket.get("source_personal_information_persisted") is not False
        or docket.get("raw_source_response_privacy_review_status")!="NOT_PERFORMED"
        or docket.get("raw_source_response_contains_personal_information") is not None
    ):
        raise CustodyIntegrityError("raw source privacy truth not accurately classified")
    # An exact canonical allowlist is verified via V15/V18 validation.
    # The original complete HTTP JSON response is transiently decoded by
    # the adapter; that full input was NOT inspected for personal information.
    controls=[]
    for control_id, action in REVIEWER_CHECKS:
        evidence=REQUIREMENTS.get(control_id)
        if evidence is None or len(evidence)!=2:
            raise CustodyIntegrityError("unknown or incomplete review control")
        controls.append({
            "control_id":control_id,
            "risk_class":RISK_CLASSES[control_id],
            "control_summary":action,
            "evidence_required":list(evidence),
            "evidence_received":False,
            "reviewer_identity_verified":False,
            "reviewer_signoff_verified":False,
            "review_status":"UNSUBMITTED_INDEPENDENT_REVIEW",
            "customer_release_authority":False,
        })
    if len(controls)!=len(REQUIREMENTS):
        raise CustodyIntegrityError("not all independent controls mapped")
    head=docket.get("canonical_head_sha256")
    seq=docket.get("canonical_head_sequence")
    if (
        not isinstance(head,str) or len(head)!=64
        or any(c not in "0123456789abcdef" for c in head)
        or type(seq) is not int or seq<0
    ):
        raise CustodyIntegrityError("untrusted custody anchor")
    scope={
        "schema_version":SCHEMA,
        "canonical_custody_head_sha256":head,
        "canonical_head_sequence":seq,
        "control_ids":[c["control_id"] for c in controls],
        "included_field_ids":sorted(PLANNING_FIELDS),
        "dataset":docket.get("dataset"),
    }
    scope_sha256=sha256(json.dumps(
        scope,sort_keys=True,ensure_ascii=True,separators=(",",":"),
        allow_nan=False,
    ).encode()).hexdigest()
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"EVIDENCE_COLLECTION_READY_RELEASE_HELD",
        "evidence_scope_sha256":scope_sha256,
        "digest_semantics":"LOCAL_UNANCHORED_DETERMINISTIC_SCOPE_NOT_SIGNATURE",
        "canonical_head_sha256":head,
        "canonical_head_sequence":seq,
        "review_controls_total":len(controls),
        "review_controls_completed":0,
        "review_controls_pending":len(controls),
        "field_scope_count":len(fields),
        "evidence_collection_tasks":controls,
        "transient_raw_response_decoded_in_memory":True,
        "transient_raw_response_privacy_review":"NOT_PERFORMED",
        "raw_source_personal_information_present":None,
        "custody_persisted_fields_allowlist_validated":True,
        "personal_contact_fields_persisted_in_custody":False,
        "unreviewed_persisted_fields_detected":False,
        "excluded_by_design":list(EXCLUDED_FIELDS),
        "correction_method_candidate":"APPEND_LATER_OBSERVATION_WITH_CLEAR_SUPERSESSION",
        "historical_source_revocation_requires_independent_policy_review":True,
        "privacy_erasure_requests_require_separate_review":True,
        "outbound_enabled":False,
        "customer_delivery_enabled":False,
        "data_resale_authorized":False,
        "model_training_approved":False,
        "payment_execution":False,
        "production_writes":False,
        "source_field_rights_cleared":False,
        "independent_reviewer_signed_off":False,
        "founder_release_approved":False,
        "execution_authority":"NONE",
    }
