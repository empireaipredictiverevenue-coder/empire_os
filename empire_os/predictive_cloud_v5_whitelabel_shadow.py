"""EmpireOS V5: read-only, nonauthoritative white-label domain preview.

Never creates a tenant, public gateway, API key, DNS/SSL, billing or DB write.
Retains original EmpireDB/CRM identity and the separate V4 Redis shadow.
"""
from __future__ import annotations
import ipaddress
import re
from uuid import UUID
from typing import Any
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA = 'empire.predictive_cloud.v5.whitelabel_shadow.v1'
BRAND_FIELDS = frozenset({'schema_version','tenant_id','brand_name','accent_hex',
                          'logo_asset_digest','custom_host','plan','synthetic_only'})
SAFE_LABEL = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')
DIGEST = re.compile(r'^[0-9a-f]{64}$')
BRAND_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .&'()_-]{1,59}$")
PLANS = frozenset({'enterprise','scale','whale','sovereign'})

class V5Hold(ValueError):
    pass

def _tenant(value: Any)->str:
    if type(value) is not str:
        raise V5Hold('v5_canonical_tenant_id_required')
    try: parsed = str(UUID(value))
    except (TypeError,ValueError,AttributeError):
        raise V5Hold('v5_canonical_tenant_id_required') from None
    if parsed!=value or parsed=='00000000-0000-0000-0000-000000000000':
        raise V5Hold('v5_canonical_tenant_id_required')
    return parsed

def _host(value: Any)->str:
    if type(value) is not str or not 4<=len(value)<=253 or value.lower()!=value:
        raise V5Hold('v5_invalid_hostname')
    if value!=value.strip() or ':' in value or '/' in value or '\\' in value:
        raise V5Hold('v5_invalid_hostname')
    try: ipaddress.ip_address(value)
    except ValueError: pass
    else: raise V5Hold('v5_ip_address_not_a_tenant_hostname')
    parts=value.split('.')
    if (not 3<=len(parts)<=8 or any(not SAFE_LABEL.fullmatch(x) or x.startswith('xn--') for x in parts)
        or parts[-1] in ('local','internal','localhost','test','invalid','example')
        or len(parts[-1])<2 or parts[-1].isdigit()
        or value.endswith('.empire-ai.co.uk')):
        raise V5Hold('v5_unverified_or_reserved_hostname')
    return value

def review_brand_candidate(value: Any)->dict[str,Any]:
    if type(value) is not dict or set(value)!=BRAND_FIELDS:
        raise V5Hold('v5_exact_brand_contract_required')
    if value['schema_version']!=SCHEMA or value['synthetic_only'] is not True:
        raise V5Hold('v5_fixture_only_brand_candidate')
    tenant=_tenant(value['tenant_id'])
    name=value['brand_name']
    if type(name) is not str or not BRAND_NAME.fullmatch(name):
        raise V5Hold('v5_invalid_brand_name')
    color=value['accent_hex']
    if type(color) is not str or not re.fullmatch(r'#[0-9a-fA-F]{6}',color):
        raise V5Hold('v5_invalid_accent_color')
    logo=value['logo_asset_digest']
    if type(logo) is not str or not DIGEST.fullmatch(logo):
        raise V5Hold('v5_opaque_logo_asset_required')
    host=_host(value['custom_host'])
    if type(value['plan']) is not str or value['plan'] not in PLANS:
        raise V5Hold('v5_supported_plan_required')
    return {'schema_version':SCHEMA,'tenant_id':tenant,'brand_name':name,
        'accent_hex':color.upper(),'logo_asset_digest':logo,'custom_host':host,
        'requested_plan':value['plan'],'status':'OWNER_REVIEW_REQUIRED',
        'domain_owner_verified':False,'ssl_active_verified':False,
        'dns_target_verified':False,'empiredb_tenant_membership_verified':False,
        'active_white_label':False,'public_api_enabled':False,
        'tenant_provisioned':False,'execution_authority':'none'}

def review_domain_evidence(candidate: dict[str,Any],*,observed_host: str,
    claimed_host_active: bool,claimed_ssl_active: bool,claimed_dns_pointed: bool)->dict[str,Any]:
    host=_host(observed_host)
    if candidate.get('status')!='OWNER_REVIEW_REQUIRED' or candidate.get('custom_host')!=host:
        raise V5Hold('v5_host_registry_conflict')
    if any(type(x) is not bool for x in (claimed_host_active,claimed_ssl_active,claimed_dns_pointed)):
        raise V5Hold('v5_boolean_domain_report_required')
    # These flags are supplied by a caller, not authenticated provider API.
    return {'status':'INDEPENDENT_DOMAIN_ATTESTATION_REQUIRED','host':host,
        'reported_host_active_untrusted':claimed_host_active,
        'reported_ssl_active_untrusted':claimed_ssl_active,
        'reported_dns_pointed_untrusted':claimed_dns_pointed,
        'resolved_tenant_id':None,'domain_route_activated':False,
        'execution_authority':'none'}

def review_signed_crm_brand_preview(*,candidate:dict[str,Any],
    verifier:SignedCrmTenantVerifier,bearer:str,untrusted_x_tenant_id:str|None=None)->dict[str,Any]:
    if not isinstance(verifier,SignedCrmTenantVerifier):
        raise V5Hold('v5_original_signed_crm_verifier_required')
    tenant=verifier.authenticate(bearer)
    if candidate.get('tenant_id')!=tenant or candidate.get('status')!='OWNER_REVIEW_REQUIRED':
        raise V5Hold('v5_signed_tenant_or_candidate_mismatch')
    if untrusted_x_tenant_id is not None and untrusted_x_tenant_id!=tenant:
        raise V5Hold('v5_untrusted_tenant_header_mismatch')
    return {'status':'SIGNED_CRM_READ_ONLY_BRAND_PREVIEW','tenant_id':tenant,
        'can_preview_unpublished_brand':True,'can_access_partner_api':False,
        'can_activate_domain':False,'can_provision_tenant':False,
        'can_dispatch_profit_router':False,'can_change_billing':False,
        'execution_authority':'none'}

def readiness()->dict[str,Any]:
    return {'schema_version':SCHEMA,'status':'WHITE_LABEL_V5_NOT_ACTIVATED',
        'canonical_database':'EmpireDB_PostgreSQL','legacy_sqlite_authoritative':False,
        'cloud_edge_connected':False,'redis_cloud_connected':False,
        'verified_custom_domains':0,'public_partner_api_enabled':False,
        'tenant_provisioning_enabled':False,'money_movement_enabled':False,
        'execution_authority':'none'}
