"""Original Predictive Cloud V5 read-only white-label/hostname isolation."""
from __future__ import annotations
import base64
import json
from uuid import uuid4
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
from empire_os.saas_scale import TenantMembership
from empire_os.predictive_cloud_v5_whitelabel_shadow import (
    SCHEMA,V5Hold,review_brand_candidate,review_domain_evidence,
    review_signed_crm_brand_preview,readiness,
)
TENANT='00000000-0000-0000-0000-000000000101'
OTHER='00000000-0000-0000-0000-000000000102'
NOW=1800000000

def candidate(**changes):
    obj={'schema_version':SCHEMA,'tenant_id':TENANT,
      'brand_name':'Original Partner Labs','accent_hex':'#376AE5',
      'logo_asset_digest':'a'*64,'custom_host':'portal.partner.example.org',
      'plan':'enterprise','synthetic_only':True}
    obj.update(changes)
    return obj

def test_candidate_is_not_an_active_white_label():
    reviewed=review_brand_candidate(candidate())
    assert reviewed['status']=='OWNER_REVIEW_REQUIRED'
    assert reviewed['tenant_id']==TENANT
    assert reviewed['active_white_label'] is False
    assert reviewed['domain_owner_verified'] is False
    assert reviewed['execution_authority']=='none'

@pytest.mark.parametrize('value',[
    '127.0.0.1','portal.local','portal.partner.local',
    'portal.partner.invalid','Portal.partner.org','https://portal.partner.org',
    'portal.partner.org:443','portal.partner.org/path',
    '*.partner.org','a..partner.org','portal.partner.org.',
    'portal.partner.org\nSet-Cookie: x','localhost',
    'a.xn--lookalike.org','portal.empire-ai.co.uk',
])
def test_untrusted_host_and_reserved_domain_refused(value):
    with pytest.raises(V5Hold):
        review_brand_candidate(candidate(custom_host=value))

@pytest.mark.parametrize('bad',[
    {'schema_version':'bad'}, {'tenant_id':'00000000-0000-0000-0000-0000000000AA'},
    {'tenant_id':'not-uuid'}, {'logo_asset_digest':'http://evil/logo.png'},
    {'brand_name':'<script>alert(1)</script>'},
    {'accent_hex':'red'}, {'accent_hex':'#ff001122'},
    {'plan':'free'}, {'synthetic_only':False},
    {'source_service_account_key':'secret'},
])
def test_untrusted_candidate_refused(bad):
    with pytest.raises(V5Hold):review_brand_candidate(candidate(**bad))

def test_reported_provider_green_status_not_host_authority():
    reviewed=review_brand_candidate(candidate())
    result=review_domain_evidence(reviewed,
      observed_host=reviewed['custom_host'],claimed_host_active=True,
      claimed_ssl_active=True,claimed_dns_pointed=True)
    assert result['reported_host_active_untrusted'] is True
    assert result['resolved_tenant_id'] is None
    assert result['domain_route_activated'] is False
    assert result['execution_authority']=='none'

def test_host_conflict_is_rejected_before_tenant_resolution():
    with pytest.raises(V5Hold,match='host_registry_conflict'):
        review_domain_evidence(review_brand_candidate(candidate()),
          observed_host='portal.other.org',claimed_host_active=True,
          claimed_ssl_active=True,claimed_dns_pointed=True)

def _b64(data):return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def _auth_token(private,tenant=TENANT):
    header={'alg':'EdDSA','typ':'JWT','kid':'test-only'}
    claims={'iss':'empire-os','aud':'empire-revenue-crm',
      'sub':'test-user','tenant_id':tenant,'scope':'crm:read',
      'iat':NOW-1,'nbf':NOW-1,'exp':NOW+100,'jti':'fixturetokenunique12345'}
    message=_b64(json.dumps(header).encode())+'.'+_b64(json.dumps(claims).encode())
    return message+'.'+_b64(private.sign(message.encode()))

def _verifier(private):
    return SignedCrmTenantVerifier({'test-only':private.public_key()},
      load_membership=lambda user,tenant:TenantMembership(
         tenant_id=tenant,user_id=user,role='viewer'),now=lambda:NOW)

def test_signed_existing_crm_read_membership_only_permits_unpublished_preview():
    private=Ed25519PrivateKey.generate()
    out=review_signed_crm_brand_preview(candidate=review_brand_candidate(candidate()),
      verifier=_verifier(private),bearer=_auth_token(private),
      untrusted_x_tenant_id=TENANT)
    assert out['tenant_id']==TENANT
    assert out['can_preview_unpublished_brand'] is True
    for key in ('can_access_partner_api','can_activate_domain','can_provision_tenant',
                'can_dispatch_profit_router','can_change_billing'):
        assert out[key] is False
    assert out['execution_authority']=='none'

def test_signed_other_tenant_is_rejected_even_if_host_matches():
    private=Ed25519PrivateKey.generate()
    with pytest.raises(V5Hold,match='tenant_or_candidate_mismatch'):
        review_signed_crm_brand_preview(candidate=review_brand_candidate(candidate()),
          verifier=_verifier(private),bearer=_auth_token(private,OTHER))

def test_signed_header_conflict_is_rejected():
    private=Ed25519PrivateKey.generate()
    with pytest.raises(V5Hold,match='tenant_header_mismatch'):
        review_signed_crm_brand_preview(candidate=review_brand_candidate(candidate()),
          verifier=_verifier(private),bearer=_auth_token(private),
          untrusted_x_tenant_id=OTHER)

def test_forged_signed_token_rejected_and_no_host_based_fallback():
    key=Ed25519PrivateKey.generate()
    with pytest.raises(ValueError):
        review_signed_crm_brand_preview(candidate=review_brand_candidate(candidate()),
          verifier=_verifier(key),bearer=_auth_token(Ed25519PrivateKey.generate()))

def test_disabled_canonical_membership_blocks_signed_preview():
    private=Ed25519PrivateKey.generate()
    verifier=SignedCrmTenantVerifier({'test-only':private.public_key()},
      load_membership=lambda user,tenant:TenantMembership(
        tenant_id=tenant,user_id=user,role='viewer',status='disabled'),now=lambda:NOW)
    with pytest.raises(ValueError,match='membership'):
        review_signed_crm_brand_preview(candidate=review_brand_candidate(candidate()),
          verifier=verifier,bearer=_auth_token(private))

def test_white_label_readiness_does_not_claim_infrastructure_or_active_tenant():
    status=readiness()
    assert status['status']=='WHITE_LABEL_V5_NOT_ACTIVATED'
    assert status['canonical_database']=='EmpireDB_PostgreSQL'
    assert status['legacy_sqlite_authoritative'] is False
    assert status['public_partner_api_enabled'] is False
    assert status['verified_custom_domains']==0
    assert status['execution_authority']=='none'


def test_original_cloud_status_contains_held_white_label_readiness(tmp_path):
    from empire_os.predictive_cloud_status import build_predictive_cloud_status
    from datetime import datetime,timezone
    status=build_predictive_cloud_status(tmp_path,now=datetime(2026,10,24,tzinfo=timezone.utc))
    assert status["v5_white_label_shadow"]["status"]=="WHITE_LABEL_V5_NOT_ACTIVATED"
    assert status["v5_white_label_shadow"]["public_partner_api_enabled"] is False
    assert status["redis_v4_shadow"]["status"]=="REDIS_CLOUD_NOT_CONNECTED"
    assert status["execution_authority"]=="none"
