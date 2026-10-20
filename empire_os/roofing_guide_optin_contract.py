"""First-party homeowner opt-in consent-state contract. No persistence or sends.

Not the B2B prospect ingestor, legacy SQLite lead lane, buyer CRM tenant
binder, or consumer-email distribution grant. All decisions are PII-free.
"""
from __future__ import annotations
from collections.abc import Mapping

SCHEMA="empire.consumer.roofing_guide_optin.v1"
RECEIPT="empire.consumer.original_roofing_optin_receipt.v1"
NOTICE="roofing-homeowner-updates-v1"


def held(reason: str)->dict:
    return {
        "schema_version":SCHEMA, "status":"HOLD",
        "reason_code":reason, "guide_access_without_email":True,
        "empire_newsletter_candidate":False,
        "named_buyer_referral_candidate":False,
        "buyer_personal_data_transfer_authorized":False,
        "marketing_email_authorized":False,
        "customer_record_created":False, "payment_authorized":False,
        "execution_authority":"none",
    }


def assess_original_receipt(proof:Mapping|None)->dict:
    if not isinstance(proof,Mapping) or proof.get("schema_version")!=RECEIPT:
        return held("NOT_ORIGINAL_FIRST_PARTY_SOURCE")
    if proof.get("offer_slug")!="roofing-cost-guide" or proof.get("notice_version")!=NOTICE:
        return held("WRONG_OFFER_OR_NOTICE_VERSION")
    checks=("first_party_form_provenance","adult_appropriate_source_verified",
            "notice_presented_before_choice","original_choice_evidence_retained",
            "suppression_checked","retention_policy_approved")
    if any(proof.get(k) is not True for k in checks):
        return held("ORIGINAL_NOTICE_OR_PRIVACY_EVIDENCE_MISSING")
    if proof.get("guide_requested") is not True:
        return held("NO_GUIDE_REQUEST")
    brand=proof.get("optional_empire_updates") is True
    referral=proof.get("optional_named_buyer_referral") is True
    if brand and proof.get("separate_brand_email_consent_verified") is not True:
        return held("BRAND_MARKETING_PERMISSION_UNVERIFIED")
    if referral and (proof.get("real_named_recipient_verified") is not True
        or proof.get("buyer_name_shown_on_form") is not True
        or proof.get("specific_buyer_channel_and_purpose_consented") is not True
        or proof.get("third_party_disclosure_rights_reviewed") is not True):
        return held("THIRD_PARTY_REFERRAL_CONSENT_UNVERIFIED")
    result=held("PENDING_INDEPENDENT_RELEASE_OWNER_CHECK")
    result.update(
        status=("NAMED_BUYER_REFERRAL_PRIVATE_REVIEW" if referral
                else "EMPIRE_UPDATES_PRIVATE_REVIEW" if brand
                else "GUIDE_ONLY_PRIVATE_REVIEW"),
        empire_newsletter_candidate=brand,
        named_buyer_referral_candidate=referral,
    )
    return result


def activation_gate(receipts:Mapping|None)->dict:
    """Review proposal; never enables a real endpoint from booleans alone."""
    requirements={
        "owner_reviewed_privacy_notice":"/privacy",
        "durable_purpose_specific_empiredb_storage":"VERIFIED",
        "withdrawal_suppression_and_deletion":"VERIFIED",
        "submission_rate_limit_and_spam_checks":"VERIFIED",
        "consent_text_immutable_custody":"VERIFIED",
        "own_brand_subscription_delivery_owner":"VERIFIED",
        "public_https_endpoint_and_attestation":"VERIFIED",
    }
    missing=sorted(
        key for key,value in requirements.items()
        if not isinstance(receipts,Mapping) or receipts.get(key)!=value
    )
    return {
        "schema_version":"empire.consumer.roofing_optin_activation.v1",
        "status":"COLLECTION_HELD_PENDING_EXTERNAL_OWNER_PROOFS",
        "collection_endpoint_public_enabled":False,
        "unsubscribe_path_verified":False if "withdrawal_suppression_and_deletion" in missing else True,
        "missing_owner_proofs":missing,
        "buyer_referral_enabled":False,
        "webhook_send_authorized":False,
        "database_writes":False,
        "execution_authority":"none",
    }
