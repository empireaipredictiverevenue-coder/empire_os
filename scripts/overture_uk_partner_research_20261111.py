"""One reviewed UK Overture partner handoff to the ORIGINAL Buyer Scout.

The original Scout is still the owner of all qualification, site evidence,
source-rights, CRM dedupe, suppression and outreach gates. This is a pinned
read-only research record, not a new provider, live browser task or buyer.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
from pathlib import Path

SOURCE=Path('/srv/empire_os/runtime/chief_of_staff/owned_source_case_review_20261111.json')
SOURCE_SHA256='738daad9deb2b5ead92ff51a927982941597b304c2d617f6e3daed94cd991772'
SCHEMA='empire.chief_of_staff.owned_source_case_review.v1'
MAX_AGE=timedelta(days=7)
EXPECTED={
 'commversion.com':'POTENTIAL_AGENCY_PARTNER_RESEARCH_ONLY',
 'kemcoplumbingandheating.co.uk':'HOLD_COMPANY_STRIKE_OFF_PROPOSAL',
 'local-roofing-london.co.uk':'HOLD_LEGAL_COMPANY_IDENTITY_UNCONFIRMED',
}


def _review(raw,now):
    if (not isinstance(raw,dict)
        or raw.get('schema_version')!=SCHEMA
        or raw.get('mode')!='OBSERVE'
        or raw.get('execution_authority')!='none'
        or raw.get('source_release')!='2026-10-21.0'
        or raw.get('source_license_and_attribution')!='https://docs.overturemaps.org/attribution/'
        or raw.get('source_count_raw')!=56
        or raw.get('first_party_named_business_count')!=3
        or raw.get('fully_canonical_CRM_dedup_verified') is not False
        or raw.get('qualified_buyers_verified')!=0
        or raw.get('outbound_sent') is not False
        or raw.get('database_writes') is not False
        or raw.get('paid_search_calls') is not False):
        raise ValueError('UNTRUSTED_UK_SOURCE_PERMISSION_OR_SCHEMA')
    ts=datetime.fromisoformat(str(raw.get('generated_at') or ''))
    if (ts.tzinfo is None or now.tzinfo is None
        or not timedelta(0)<=now.astimezone(timezone.utc)-ts.astimezone(timezone.utc)<=MAX_AGE):
        raise ValueError('STALE_OR_UNTRUSTED_UK_SOURCE_TIME')
    rows=raw.get('candidate_cases')
    if not isinstance(rows,list) or len(rows)!=3 or any(not isinstance(r,dict) for r in rows):
        raise ValueError('UNBOUNDED_UK_SOURCE')
    found={r.get('domain'):r for r in rows}
    if (len(found)!=3 or set(found)!=set(EXPECTED)
        or any(found[domain].get('research_status')!=status
               for domain,status in EXPECTED.items())):
        raise ValueError('TAMPERED_UK_SOURCE_CASES')
    for case in rows:
        if (case.get('buyer_intent_verified') is not False
            or case.get('buying_authority_verified') is not False
            or case.get('contact_permission_verified') is not False
            or case.get('crm_duplicate_clearance_verified') is not False
            or case.get('outreach_authorized') is not False
            or case.get('legal_entity_identical_to_domain_owner_verified') is not False):
            raise ValueError('UNTRUSTED_UK_SOURCE_APPROVAL')
    partner=found['commversion.com']
    if (partner.get('name')!='CommVersion'
        or partner.get('company_number_official_source')!='10409312'
        or partner.get('company_status_official_source')!='active'
        or partner.get('official_registry_url')!='https://find-and-update.company-information.service.gov.uk/company/10409312'
        or partner.get('public_first_party_url')!='https://www.commversion.com/partner'
        or partner.get('source_file_sha256')!='7f23a4e766af203a88b4286a0d504f9dfb1df70cf98291964b1b726faa3bfb81'):
        raise ValueError('UK_PARTNER_COMPANY_EVIDENCE_UNTRUSTED')
    return [{
        'domain':'commversion.com', 'website':'https://www.commversion.com/partner',
        'registry_business_name':'CommVersion',
        'registry_location':'London, UK (service website and published register name; territorial scope unverified)',
        'target_markets':['UK'],
        'target_buyer_pools':['agency_partners'],
        'target_product_codes':['managed_service'],
        'source_refs':['public:overture_places:2026-10-21.0:commversion.com',
                       'public:uk_companies_house:10409312'],
        'source_queries':[], 'target_corridor_keys':[],
        'source_origin':'Overture Maps Places + first-party partner page + official company-name registry',
        'truth_class':'RESEARCH_ONLY_POTENTIAL_PARTNER_NOT_BUYER',
        'company_identity_verified':False,
        'canonical_crm_duplicate_status':'UNKNOWN_NOT_QUERIED',
        'contact_permission_verified':False, 'outreach_authorized':False,
        'verified_product_purchasing_agreement':False,
        'verified_buyer_capacity':False,'commercial_terms_verified':False,
        'buyer_price_verified':False,'execution_authority':'none',
    }]


def read_partner(*,now=None,source=SOURCE,expected_sha256=SOURCE_SHA256):
    """Return zero or one original Scout *research* seed, never a buyer."""
    now=now or datetime.now(timezone.utc)
    try:
        if (source.is_symlink() or not source.is_file()
            or not 0<source.stat().st_size<60000):
            raise ValueError('NO_TRUSTED_UK_SOURCE')
        payload=source.read_bytes()
        if sha256(payload).hexdigest()!=expected_sha256:
            raise ValueError('UK_SOURCE_DIGEST_CHANGED')
        rows=_review(json.loads(payload),now)
        return rows, {'status':'UK_OVERTURE_PARTNER_RESEARCH_ONLY',
                      'source_count':len(rows),'held_other_source_cases':2,
                      'canonical_CRM_dedup_verified':False,
                      'outreach_authorized':False,'qualified_buyers':0,
                      'execution_authority':'none'}
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        return [], {'status':'UK_OVERTURE_PARTNER_SOURCE_HELD',
                    'source_count':0,'qualified_buyers':0,
                    'outreach_authorized':False,'execution_authority':'none'}
