from datetime import datetime, timedelta, timezone
import copy

from empire_os.gtm_ops_first_sale_source import assess_owner_ops, observe_owner_ops_first_sale

NOW=datetime(2026,10,23,11,46,tzinfo=timezone.utc)


def owner_packet(n=0):
    return {
        "schema_version":"empire.ops_control_cycle.v1",
        "mode":"OBSERVE", "observed_at":NOW.isoformat(),
        "first_sale_conversion_readiness":{
            "schema_version":"empire.commercial.first_sale_live_conversion_observer.v1",
            "mode":"OBSERVE","execution_authority":"none",
            "status":("NO_CANONICAL_FIRST_PARTY_SALES_ENQUIRIES"
                      if n == 0 else "FIRST_PARTY_ENQUIRY_PRESENT_OWNER_REVIEW_REQUIRED"),
            "outbound_sent":False,"crm_mutations":False,
            "database_writes":False,"payment_action":False,
            "public_post_or_customer_submission_attempted":False,
            "first_party_source_count_not_authenticated_buyer":True,
            "verified_first_sale":None,"recognized_revenue_cents":None,
            "canonical_sales_acquisition_counts":{
                "commercial_acquisition_rows":n,
                "predictive_acquisition_rows":0,
                "sales_acquisition_rows":n,
                "distinct_sales_prospects":n,
                "source_evidence_consistent_rows":n,
                "entity_unlinked_acquisition_rows":0,
                "founder_binding_exact_one_rows":n,
                "founder_binding_missing_or_ambiguous_rows":0,
            },
        },
    }


def test_real_zero_source_count_not_represented_as_unknown():
    output=assess_owner_ops(owner_packet(),now=NOW)
    assert output["status"]=="CANONICAL_COMMERCIAL_SALES_INTAKE_ZERO_OBSERVED"
    assert output["source_count_verified"] is True
    assert output["canonical_commercial_enquiries"]==0
    assert output["canonical_predictive_revenue_enquiries"]==0
    assert output["exact_crm_readback_verified"] is False
    assert output["specific_response_consent_current_verified"] is False
    assert output["outreach_authorized"] is False


def test_nonzero_source_never_claims_buyer_or_contact_authority():
    output=assess_owner_ops(owner_packet(2),now=NOW)
    assert output["canonical_sales_acquisitions"]==2
    assert output["status"]=="CANONICAL_SALES_ENQUIRIES_PRESENT_EXACT_READBACK_REQUIRED"
    assert output["individual_buyer_identity_verified"] is False
    assert output["exact_crm_readback_verified"] is False
    assert output["payments_authorized"] is False


def test_missing_owner_snapshot_stays_unknown(tmp_path):
    output=observe_owner_ops_first_sale(tmp_path,now=NOW)
    assert output["canonical_sales_acquisitions"] is None
    assert output["source_count_verified"] is False


def test_stale_or_untrusted_root_source_rejected():
    changes=[
        ("schema_version","not_empire"),
        ("mode","ACT"),
        ("observed_at",(NOW-timedelta(days=2)).isoformat()),
    ]
    for key, value in changes:
        altered=owner_packet()
        altered[key]=value
        assert assess_owner_ops(altered,now=NOW)["source_count_verified"] is False
    for key,value in (
        ("execution_authority","send"),
        ("payment_action",True),
        ("crm_mutations",True),
        ("verified_first_sale",True),
        ("public_post_or_customer_submission_attempted",True),
        ("status","BUYERS_VERIFIED"),
    ):
        altered=owner_packet()
        altered["first_sale_conversion_readiness"][key]=value
        assert assess_owner_ops(altered,now=NOW)["source_count_verified"] is False, key


def test_contradictory_counters_or_false_zero_rejected():
    changed=owner_packet()
    changed["first_sale_conversion_readiness"]["canonical_sales_acquisition_counts"]["sales_acquisition_rows"]=1
    assert assess_owner_ops(changed,now=NOW)["source_count_verified"] is False
    changed=owner_packet(1)
    changed["first_sale_conversion_readiness"]["canonical_sales_acquisition_counts"]["source_evidence_consistent_rows"]=4
    assert assess_owner_ops(changed,now=NOW)["source_count_verified"] is False
