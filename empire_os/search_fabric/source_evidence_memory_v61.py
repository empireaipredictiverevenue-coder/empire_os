"""Durable original Search Fabric review-only memory; never identity promotion.

Consumed by the ORIGINAL Search Fabric runner and downstream evidence readers.
The data is not a new database, lead source or authority for contact/resale.
"""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping
import re,uuid,hashlib,json

SCHEMA='empire.search_fabric.original_evidence_memory.v61'
STATUS=frozenset({
 'FIRST_PARTY_NAME_AND_PHONE_OBSERVED_REVIEW_ONLY',
 'FIRST_PARTY_BUSINESS_NAME_OBSERVED_REVIEW_ONLY',
 'FIRST_PARTY_NAME_NOT_CORROBORATED',
 'SITE_REDIRECT_IDENTITY_HOLD',
 'SITE_PROBE_FAILED',
 'SOURCE_RIGHTS_OR_ROBOTS_HOLD',
 'PUBLIC_SITE_PROBE_EXCEPTION_REVIEW',
})


def validate_observation(value:Any)->dict[str,Any]:
    if not isinstance(value,dict):raise ValueError('SOURCE_V61_OBSERVATION_UNTRUSTED')
    uid=str(uuid.UUID(str(value.get('prospect_id'))))
    status=value.get('research_status')
    digest=value.get('source_hostname_sha256')
    name=value.get('first_party_company_name_correlated',False)
    phone=value.get('first_party_phone_last_ten_observed',False)
    # Archived original V60 receipts erroneously flagged this status as a
    # positive name match. Accept that exact legacy shape for replay, but
    # normalise it to FALSE; never reissue false identity evidence.
    corroborated = status in {
        'FIRST_PARTY_NAME_AND_PHONE_OBSERVED_REVIEW_ONLY',
        'FIRST_PARTY_BUSINESS_NAME_OBSERVED_REVIEW_ONLY'}
    legacy_misflag = status == 'FIRST_PARTY_NAME_NOT_CORROBORATED' and name is True
    if (status not in STATUS or type(digest) is not str
        or re.fullmatch('[a-f0-9]{64}',digest) is None
        or type(name) is not bool or type(phone) is not bool
        or phone != (status=='FIRST_PARTY_NAME_AND_PHONE_OBSERVED_REVIEW_ONLY')
        or (name != corroborated and not legacy_misflag)
        or value.get('legal_company_verified') is not False
        or value.get('buyer_or_contact_permission_verified') is not False):
        raise ValueError('SOURCE_V61_UNSAFE_OR_UNVERIFIED_OBSERVATION')
    gaps=value.get('missing_prior_evidence') or []
    permitted={'MISSING_ACCEPTED_ACQUISITION_PROVENANCE','MISSING_VERIFIED_ENTITY_LINK',
               'V2_NOT_YET_SCORED_DIFFERENT_OWNER','MISSING_TAXONOMY'}
    if not isinstance(gaps,list) or len(gaps)>4 or any(v not in permitted for v in gaps):
        raise ValueError('SOURCE_V61_UNKNOWN_EVIDENCE_GAP')
    return {'prospect_id':uid,'source_hostname_sha256':digest,
       'research_status':status,'observed_name':corroborated,'observed_phone_last_ten':phone,
       'missing_original_evidence':sorted(set(gaps)),
       'independent_legal_identity_verified':False,
       'independent_niche_provenance_verified':False,
       'source_resale_rights_verified':False,
       'contact_permission_verified':False,
       'automatic_original_record_promotion_authorized':False}


def reconcile(*,history:Mapping[str,Any]|None,report:Mapping[str,Any],cycle:int)->dict[str,Any]:
    if (type(cycle) is not int or not 1<=cycle<=10000000
      or not isinstance(report,Mapping)
      or report.get('schema_version')!='empire.search_fabric.original_automated_source_recovery.v60'
      or report.get('mode')!='AUTONOMOUS_ORIGINAL_SEARCH_FABRIC_EVIDENCE_RECOVERY_OBSERVE'
      or report.get('database_writes') is not False
      or report.get('new_outbound_sent') != 0):
        raise ValueError('SOURCE_V61_REPORT_CONTRACT_UNTRUSTED')
    observed_at=str(report.get('observed_at_utc') or '')
    try:observed=datetime.fromisoformat(observed_at.replace('Z','+00:00'))
    except ValueError:raise ValueError('SOURCE_V61_OBSERVATION_TIME_INVALID')
    if observed.tzinfo is None:raise ValueError('SOURCE_V61_OBSERVATION_TIME_INVALID')
    items=report.get('review_only_prospect_evidence')
    if not isinstance(items,list) or len(items)>12 or len(items)!=report.get('official_sites_attempted'):
        raise ValueError('SOURCE_V61_OBSERVATION_COUNT_INVALID')
    old=history if history is not None else {'schema_version':SCHEMA,'cycles_recorded':0,'prospects':{}}
    if old.get('schema_version')!=SCHEMA or not isinstance(old.get('prospects'),dict):
        raise ValueError('SOURCE_V61_PRIOR_MEMORY_UNTRUSTED')
    prev=old.get('cycles_recorded')
    if type(prev) is not int or not 0<=prev<cycle:
        raise ValueError('SOURCE_V61_CYCLE_REPLAY_OR_ROLLBACK')
    if len(old['prospects'])>40000:raise ValueError('SOURCE_V61_MEMORY_CAP_EXCEEDED')
    memory=dict(old['prospects']);seen=set()
    observed_rows=[]
    for raw in items:
        row=validate_observation(raw)
        identity=row['prospect_id'];seen.add(identity)
        prior=memory.get(identity) or {}
        if prior and (prior.get('independent_legal_identity_verified') is not False
                      or prior.get('automatic_original_record_promotion_authorized') is not False):
            raise ValueError('SOURCE_V61_PRIOR_MEMORY_AUTHORITY_INVALID')
        updated={'prospect_id':identity,'last_observed_at_utc':observed.isoformat(),
          'last_cycle':cycle,'source_hostname_sha256':row['source_hostname_sha256'],
          'research_status':row['research_status'],
          'observed_name':row['observed_name'],
          'observed_phone_last_ten':row['observed_phone_last_ten'],
          'missing_original_evidence':row['missing_original_evidence'],
          'source_observation_count':int(prior.get('source_observation_count') or 0)+1,
          'independent_legal_identity_verified':False,
          'independent_niche_provenance_verified':False,
          'source_resale_rights_verified':False,
          'contact_permission_verified':False,
          'automatic_original_record_promotion_authorized':False}
        memory[identity]=updated
        observed_rows.append(updated)
    if len(seen)!=len(items):raise ValueError('SOURCE_V61_DUPLICATE_PROSPECT_SAME_CYCLE')
    if len(memory)>40000:raise ValueError('SOURCE_V61_MEMORY_CAP_EXCEEDED')
    return {'schema_version':SCHEMA,'mode':'READ_ONLY_FIRST_PARTY_SEARCH_EVIDENCE_MEMORY',
      'cycles_recorded':cycle,'distinct_prospects_observed':len(memory),
      'last_cycle_at_utc':observed.isoformat(),
      'prospects':memory,'last_cycle_observations':observed_rows,
      'legal_entity_merges':0,'prospect_data_updates':0,
      'source_rights_or_contact_authorization_assumed':False,
      'buyer_outreach_or_revenue_triggered':False}


def digest(obj:Mapping[str,Any])->str:
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()
