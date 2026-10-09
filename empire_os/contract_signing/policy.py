"""Deterministic Documenso signing policy. No network, approval or signing."""
from __future__ import annotations
from collections.abc import Mapping
import re

SCHEMA = "empire.contract_signing.documenso_preflight.v1"
TYPES = frozenset({
    "contractor_growth", "customer_subscription", "nda", "master_services_agreement",
    "statement_of_work", "carrier_partnership", "supplier_agreement",
    "affiliate_publisher", "white_label", "enterprise", "licensed_claims_services",
})
ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{2,127}$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")


def valid_id(item: object) -> bool:
    return isinstance(item, str) and bool(ID.fullmatch(item))


def prepare_agreement(record: Mapping) -> dict:
    """Approved document hash + verified parties + reviewed terms required.

    READY means only ready to REQUEST founder signing release; it never
    authorises distribution, signature, or acceptance of binding terms.
    """
    if not isinstance(record, Mapping):
        raise TypeError("AGREEMENT_REQUIRES_OBJECT")
    missing = set()
    for key in ("agreement_id", "tenant_id", "counterparty_entity_id"):
        if not valid_id(record.get(key)):
            missing.add("INVALID_" + key.upper())
    kind = record.get("contract_type")
    if kind not in TYPES:
        missing.add("INVALID_CONTRACT_TYPE")
    if record.get("provider") != "documenso":
        missing.add("DOCUMENSO_ONLY")
    if not isinstance(record.get("jurisdiction"), str) or not record["jurisdiction"].strip():
        missing.add("JURISDICTION_MISSING")
    if not isinstance(record.get("approved_pdf_sha256"), str) or not DIGEST.fullmatch(record["approved_pdf_sha256"]):
        missing.add("SIGNED_SOURCE_PDF_DIGEST_MISSING")
    version = record.get("agreement_version")
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        missing.add("INVALID_AGREEMENT_VERSION")
    parties = record.get("signers")
    if not isinstance(parties, list) or len(parties) != 2:
        missing.add("REQUIRES_TWO_VERIFIED_PARTIES")
    else:
        roles = [p.get("role") if isinstance(p, Mapping) else None for p in parties]
        if set(roles) != {"FOUNDER", "COUNTERPARTY"}:
            missing.add("FOUNDER_AND_COUNTERPARTY_ROLES_REQUIRED")
        if any(not isinstance(p, Mapping) or not valid_id(p.get("entity_id"))
               or p.get("identity_verified") is not True for p in parties):
            missing.add("UNVERIFIED_SIGNER_IDENTITY")
        elif parties[0]["entity_id"] == parties[1]["entity_id"]:
            missing.add("SIGNERS_MUST_BE_DIFFERENT_ENTITIES")
    for flag, reason in (
        ("legal_review_approved", "LEGAL_REVIEW_REQUIRED"),
        ("founder_approved", "FOUNDER_REVIEW_REQUIRED"),
        ("terms_binding", "FINAL_TERMS_MISSING"),
        ("delivery_permission_checked", "DELIVERY_PERMISSION_REQUIRED"),
    ):
        if record.get(flag) is not True:
            missing.add(reason)
    if kind == "licensed_claims_services" or record.get("claim_contingent_compensation") is True:
        missing.add("CLAIMS_LICENSING_AND_FEE_LEGAL_CLEARANCE_REQUIRED")
    if record.get("automated_signing_requested") is True:
        missing.add("AUTOMATED_SIGNATURE_FORBIDDEN")
    return {
        "schema": SCHEMA, "provider": "documenso", "mode": "OBSERVE",
        "agreement_id": record.get("agreement_id") if valid_id(record.get("agreement_id")) else None,
        "tenant_id": record.get("tenant_id") if valid_id(record.get("tenant_id")) else None,
        "contract_type": kind if kind in TYPES else None,
        "approved_pdf_sha256": record.get("approved_pdf_sha256") if not "SIGNED_SOURCE_PDF_DIGEST_MISSING" in missing else None,
        "state": "READY_FOR_FOUNDER_SIGNING_RELEASE_REVIEW" if not missing else "BLOCKED",
        "blockers": sorted(missing),
        "signatures_executed": False, "envelope_create_authorized": False,
        "envelope_distribute_authorized": False,
        "outbound_authorized": False, "binding_terms_accepted": False,
        "payment_authorized": False, "execution_authority": "none",
    }
