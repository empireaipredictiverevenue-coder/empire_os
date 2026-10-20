from empire_os.roofing_guide_optin_contract import assess_original_receipt, activation_gate

def receipt(**changes):
    data = dict(
        schema_version="empire.consumer.original_roofing_optin_receipt.v1",
        offer_slug="roofing-cost-guide",notice_version="roofing-homeowner-updates-v1",
        first_party_form_provenance=True,
        adult_appropriate_source_verified=True,
        notice_presented_before_choice=True,
        original_choice_evidence_retained=True,
        suppression_checked=True,
        retention_policy_approved=True,
        guide_requested=True,
        optional_empire_updates=False,
        optional_named_buyer_referral=False,
    )
    data.update(changes)
    return data


def test_free_guide_has_no_forced_marketing_or_buyer_referral():
    out=assess_original_receipt(receipt())
    assert out["guide_access_without_email"]
    assert out["status"]=="GUIDE_ONLY_PRIVATE_REVIEW"
    assert not out["empire_newsletter_candidate"]
    assert not out["named_buyer_referral_candidate"]
    assert not out["buyer_personal_data_transfer_authorized"]


def test_own_brand_optional_updates_not_buyer_sharing():
    out=assess_original_receipt(receipt(optional_empire_updates=True,
        separate_brand_email_consent_verified=True))
    assert out["status"]=="EMPIRE_UPDATES_PRIVATE_REVIEW"
    assert out["empire_newsletter_candidate"]
    assert not out["named_buyer_referral_candidate"]
    assert not out["marketing_email_authorized"]


def test_marketing_checkbox_no_proof_never_upgrades_permission():
    out=assess_original_receipt(receipt(optional_empire_updates=True))
    assert out["status"]=="HOLD"


def test_named_recipient_referral_requires_every_independent_consent_proof():
    fields=("real_named_recipient_verified","buyer_name_shown_on_form",
        "specific_buyer_channel_and_purpose_consented",
        "third_party_disclosure_rights_reviewed")
    base=receipt(optional_named_buyer_referral=True,**{field:True for field in fields})
    out=assess_original_receipt(base)
    assert out["status"]=="NAMED_BUYER_REFERRAL_PRIVATE_REVIEW"
    assert not out["buyer_personal_data_transfer_authorized"]
    for field in fields:
        changed=dict(base)
        changed[field]=False
        assert assess_original_receipt(changed)["status"]=="HOLD"


def test_wrong_source_notice_or_suppression_holds():
    for args in (
        {"schema_version":"unknown"},
        {"notice_version":"unknown"},
        {"offer_slug":"some-other-guide"},
        {"suppression_checked":False},
        {"retention_policy_approved":False},
        {"original_choice_evidence_retained":False},
        {"guide_requested":False},
    ):
        assert assess_original_receipt(receipt(**args))["status"]=="HOLD"


def test_contact_details_never_emitted_in_review():
    out=assess_original_receipt(receipt(email="synthetic-contact@example.test",
        name="Synthetic Consumer",phone="000-0000000"))
    assert "synthetic-contact" not in str(out)
    assert "Synthetic Consumer" not in str(out)
    assert "000-0000000" not in str(out)


def test_activation_is_held_even_with_fake_complete_receipt():
    fields=("owner_reviewed_privacy_notice",
        "durable_purpose_specific_empiredb_storage",
        "withdrawal_suppression_and_deletion",
        "submission_rate_limit_and_spam_checks",
        "consent_text_immutable_custody",
        "own_brand_subscription_delivery_owner",
        "public_https_endpoint_and_attestation")
    fake={x:"VERIFIED" for x in fields}
    fake["owner_reviewed_privacy_notice"]="/privacy"
    out=activation_gate(fake)
    assert out["status"]=="COLLECTION_HELD_PENDING_EXTERNAL_OWNER_PROOFS"
    assert not out["collection_endpoint_public_enabled"]
    assert not out["database_writes"]
    assert not out["buyer_referral_enabled"]


def test_missing_owner_proofs_made_explicit():
    out=activation_gate(None)
    assert len(out["missing_owner_proofs"])==7
    assert out["execution_authority"]=="none"
