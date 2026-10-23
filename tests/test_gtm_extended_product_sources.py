from datetime import datetime, timezone
import json
from empire_os.gtm_extended_product_sources import review_media, review_contractor, observe_extended_products

NOW=datetime(2026,10,23,8,0,tzinfo=timezone.utc)


def test_media_readonly_status_only():
    src={'schema_version':'empire.media_os.runtime.v1', 'mode':'OBSERVE',
         'execution_authority':'none','actual_revenue':False,
         'database_write_performed':False,'external_action_performed':False,
         'public_publish_authorized':False,'observed_source_count':3}
    output=review_media(src)
    assert output['source_count']==3
    assert output['enquiry_proven'] is False
    assert output['causal_attribution_proven'] is False
    src['public_publish_authorized']=True
    assert review_media(src)['source_count'] is None


def test_contractor_research_not_a_consenting_job_customer():
    src={'schema_version':'empire.contractor_autonomous_research.v1',
         'status':'RESEARCH_READY','mode':'OBSERVE','execution_authority':'none',
         'provider_registry_connected':False,'public_api_exposure_enabled':False,
         'live_outbound':False,'bids_submitted':0,'crm_writes':0,
         'realised_revenue':0,'bid_readiness':{'candidate_count':2}}
    output=review_contractor(src)
    assert output['research_candidate_count']==2
    assert output['job_receipt_verified'] is False
    assert output['signed_installer_verified'] is False
    src['live_outbound']=True
    assert review_contractor(src)['research_candidate_count'] is None


def test_absent_owner_receipts_stay_held(tmp_path):
    out=observe_extended_products(tmp_path,now=NOW)
    assert out['media_os']['source_count'] is None
    assert out['contractor_research']['research_candidate_count'] is None
    assert out['agency']['tenant_authority_verified'] is False
    assert out['job_matching']['paid_matching_verified'] is False
    assert out['crm_write_performed'] is False
    assert out['outreach_sent'] is False
    assert out['payment_action'] is False
