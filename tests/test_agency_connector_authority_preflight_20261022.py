"""Agency-specific signed connector authority uses canonical tenant policy, never CRM audience."""
import base64
import json
import os
from dataclasses import replace
from pathlib import Path
import secrets
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from empire_os.saas_scale import TenantMembership
from empire_os.agency_connector_authority import (
    AgencySiteGrant, authorize_agency_connector, SCHEMA, AUDIENCE, ISSUER,
    DOMAIN, OPERATIONS,
)
from empire_os.agency_connector_credentials import read_private_connector_password

TENANT="12a9875c-20f2-4e96-9e37-54b295bb146b"
SITE="synthetic-yard"
CONNECTOR="synthetic-wordpress-inventory-v1"
REF="agency-wordpress-test-password"
ORIGIN="http://127.0.0.1:24791"
USER="synthetic-admin"
NOW=1_800_000_000

@pytest.fixture()
def source():
    key=Ed25519PrivateKey.generate()
    public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    values={
        "schema":SCHEMA,"aud":AUDIENCE,"iss":ISSUER,"sub":USER,
        "tenant_id":TENANT,"site_id":SITE,"connector_id":CONNECTOR,
        "credential_ref":REF,"wp_origin":ORIGIN,"operations":list(OPERATIONS),
        "iat":NOW-20,"nbf":NOW-20,"exp":NOW+90,
        "jti":secrets.token_urlsafe(24),
    }
    state={"membership_status":"active","grant_status":"active","nonces":set(),"reader_calls":0}
    def sign(claims):
        message=DOMAIN+json.dumps(claims,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
        signature=base64.urlsafe_b64encode(key.sign(message)).rstrip(b"=").decode("ascii")
        return {"kid":"test-authority","payload":claims,"signature":signature}
    def membership(user,tenant):
        state["reader_calls"]+=1
        return TenantMembership(tenant_id=tenant,user_id=user,role="owner",status=state["membership_status"])
    def grant(user,tenant,site,connector):
        # Trusted fixture registry is fixed. Never manufacture a grant from
        # the lookup's caller-controlled requested site/connector.
        if (user,tenant,site,connector)!=(USER,TENANT,SITE,CONNECTOR):
            return None
        return AgencySiteGrant(user_id=USER,tenant_id=TENANT,site_id=SITE,
                connector_id=CONNECTOR,credential_ref=REF,wp_origin=ORIGIN,
                status=state["grant_status"],operations=OPERATIONS)
    def nonce(value):
        if value in state["nonces"]:return False
        state["nonces"].add(value)
        return True
    def verify(envelope=None,**kwargs):
        return authorize_agency_connector(
            sign(values) if envelope is None else envelope,
            pinned_authority_keys={"test-authority":public},
            membership_reader=membership,site_grant_reader=grant,
            consume_nonce=nonce,now=lambda:NOW,**kwargs
        )
    return values,state,sign,verify

def test_agency_signature_fresh_membership_site_grant_and_read_only_scope(source):
    claims,state,sign,verify=source
    result=verify()
    assert result.tenant_id==TENANT and result.site_id==SITE
    assert result.operations==OPERATIONS
    assert result.credential_ref==REF and result.wp_origin==ORIGIN
    assert state["reader_calls"]==1

@pytest.mark.parametrize("changes",[
    {"aud":"empire-revenue-crm"},{"operations":["vehicles:write"]},
    {"tenant_id":"another-tenant"},{"site_id":"different-site"},
    {"connector_id":"someone-elses-connector"},
    {"credential_ref":"another-password"},
    {"wp_origin":"https://external-wordpress.invalid"},
    {"exp":NOW-1},{"exp":NOW+900},{"nbf":NOW+10},
    {"sub":"?"},{"jti":"short"}
])
def test_signed_but_incorrect_purpose_site_or_permissions_rejected(source,changes):
    claims,state,sign,verify=source
    with pytest.raises(ValueError):
        verify(sign({**claims,**changes}))

def test_signature_tamper_and_unknown_issuer_fail_before_membership(source):
    claims,state,sign,verify=source
    envelope=sign(claims)
    envelope["payload"]={**claims,"site_id":"tampered-site"}
    with pytest.raises(ValueError):verify(envelope)
    assert state["reader_calls"]==0
    with pytest.raises(ValueError):verify({**sign(claims),"kid":"rogue-key"})

def test_fresh_canonical_membership_and_site_revocation_fail_closed(source):
    claims,state,sign,verify=source
    state["membership_status"]="disabled"
    with pytest.raises(ValueError):verify()
    state["membership_status"]="active"
    state["grant_status"]="revoked"
    with pytest.raises(ValueError):verify()

def test_jti_replay_denied_even_for_valid_signature(source):
    claims,state,sign,verify=source
    envelope=sign(claims)
    assert verify(envelope).site_id==SITE
    with pytest.raises(ValueError):verify(envelope)

def test_missing_authoritative_dependencies_fail_closed(source):
    claims,state,sign,verify=source
    with pytest.raises(ValueError):
        authorize_agency_connector(sign(claims),pinned_authority_keys={},
                membership_reader=lambda *_:None, site_grant_reader=lambda *_:None,
                consume_nonce=lambda _:True,now=lambda:NOW)

def test_ephemeral_file_credential_rotation_and_revocation(tmp_path:Path):
    base=tmp_path/"secret_mount"
    base.mkdir(mode=0o700)
    path=base/REF
    def install(secret):
        path.write_text(secret)
        path.chmod(0o600)
    install("synthetic staging word press password 123")
    value=read_private_connector_password(trusted_directory=base,credential_ref=REF,trusted_uid=os.getuid())
    assert value=="synthetic staging word press password 123"
    install("rotated staging word press password 456")
    rotated=read_private_connector_password(trusted_directory=base,credential_ref=REF,trusted_uid=os.getuid())
    assert rotated!=value
    path.unlink()
    with pytest.raises(ValueError):
        read_private_connector_password(trusted_directory=base,credential_ref=REF,trusted_uid=os.getuid())

def test_reject_world_readable_symlink_escape_bad_filename_and_wrong_owner(tmp_path:Path):
    base=tmp_path/"credentials"
    base.mkdir(mode=0o700)
    target=base/REF
    target.write_text("synthetic password 1234567890")
    target.chmod(0o644)
    with pytest.raises(ValueError):read_private_connector_password(trusted_directory=base,credential_ref=REF,trusted_uid=os.getuid())
    target.chmod(0o600)
    with pytest.raises(ValueError):read_private_connector_password(trusted_directory=base,credential_ref="../outside",trusted_uid=os.getuid())
    with pytest.raises(ValueError):read_private_connector_password(trusted_directory=base,credential_ref=REF,trusted_uid=os.getuid()+1)
    target.unlink()
    (tmp_path/"outside").write_text("staging secret 1234567890")
    target.symlink_to(tmp_path/"outside")
    with pytest.raises(ValueError):read_private_connector_password(trusted_directory=base,credential_ref=REF,trusted_uid=os.getuid())

def test_crm_token_must_not_be_treated_as_agency_authority(source):
    claims,state,sign,verify=source
    token=f"eyJhbGciOiJFZERTQSJ9.{secrets.token_urlsafe(32)}.{secrets.token_urlsafe(64)}"
    with pytest.raises(ValueError):
        authorize_agency_connector(token,pinned_authority_keys={},
          membership_reader=lambda *_:None,site_grant_reader=lambda *_:None,
          consume_nonce=lambda _:True)

from empire_os.agency_connector_preflight import (
    CanonicalConnectorBinding, prepare_agency_read_session,
)

def _prepared_session_fixture(source,tmp_path):
    claims,state,sign,verify=source
    directory=tmp_path/"agency-private-credentials"
    directory.mkdir(mode=0o700)
    secret=directory/REF
    secret.write_text("synthetic agency staging password 12345")
    secret.chmod(0o600)
    key=Ed25519PrivateKey.generate()
    public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    envelope_claims={**claims,"jti":secrets.token_urlsafe(32)}
    def signer(c):
        raw=DOMAIN+json.dumps(c,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
        signature=base64.urlsafe_b64encode(key.sign(raw)).rstrip(b"=").decode()
        return {"kid":"trusted-staging","payload":c,"signature":signature}
    canonical_memberships={"active":True}
    canonical_registry={"active":True,"credential_ref":REF}
    nonces=set()
    def membership(user,tenant):
        if not canonical_memberships["active"] or (user,tenant)!=(USER,TENANT):
            return None
        return TenantMembership(tenant_id=TENANT,user_id=USER,role="owner")
    def grant(user,tenant,site,connector):
        if not canonical_memberships["active"] or (user,tenant,site,connector)!=(USER,TENANT,SITE,CONNECTOR):
            return None
        return AgencySiteGrant(
            user_id=USER,tenant_id=TENANT,site_id=SITE,connector_id=CONNECTOR,
            credential_ref=REF,wp_origin=ORIGIN,status="active",operations=OPERATIONS)
    def registry(tenant,site,connector):
        if (tenant,site,connector)!=(TENANT,SITE,CONNECTOR):
            return None
        return CanonicalConnectorBinding(
            tenant_id=TENANT,site_id=SITE,connector_id=CONNECTOR,
            credential_ref=canonical_registry["credential_ref"],wp_origin=ORIGIN,
            allowed_operations=OPERATIONS,active=canonical_registry["active"],
            read_only=True)
    def nonce(value):
        if value in nonces:return False
        nonces.add(value)
        return True
    def prepare(newclaims=None):
        return prepare_agency_read_session(
            signer(newclaims or envelope_claims),
            pinned_authority_keys={"trusted-staging":public},
            membership_reader=membership,site_grant_reader=grant,
            trusted_registry_reader=registry,consume_nonce=nonce,
            trusted_credential_directory=directory,trusted_uid=os.getuid(),
            now=lambda:NOW)
    return prepare,canonical_memberships,canonical_registry,secret,envelope_claims

def test_three_way_signed_membership_registry_and_credential_preflight(source,tmp_path):
    prepare,member,registry,secret,claims=_prepared_session_fixture(source,tmp_path)
    session=prepare()
    assert session.authority.site_id==SITE
    assert session._application_password=="synthetic agency staging password 12345"
    assert "synthetic agency staging password" not in repr(session)
    assert "synthetic agency staging password" not in json.dumps(session.nonsecret_receipt())
    assert session.nonsecret_receipt()["credential_contents_exposed"] is False

def test_revoked_membership_registry_and_secret_fail_before_launch(source,tmp_path):
    prepare,member,registry,secret,claims=_prepared_session_fixture(source,tmp_path)
    member["active"]=False
    with pytest.raises(ValueError):prepare()
    member["active"]=True
    registry["active"]=False
    with pytest.raises(ValueError):prepare()
    registry["active"]=True
    registry["credential_ref"]="another-connector-secret"
    with pytest.raises(ValueError):prepare()
    registry["credential_ref"]=REF
    secret.chmod(0o644)
    with pytest.raises(ValueError):prepare()

def test_cross_tenant_signed_grant_cannot_select_different_site_registry(source,tmp_path):
    prepare,member,registry,secret,claims=_prepared_session_fixture(source,tmp_path)
    with pytest.raises(ValueError):prepare({**claims,"site_id":"someone-else-site"})
    with pytest.raises(ValueError):prepare({**claims,"tenant_id":"5e8d111a-6785-4c79-8841-1542a6b9cd66"})

def test_preflight_is_separate_from_unapproved_live_service():
    import inspect
    from empire_os.agency_connector_preflight import prepare_agency_read_session
    source=inspect.getsource(prepare_agency_read_session)
    assert "subprocess" not in source and "Popen" not in source
    assert "read_private_connector_password" in source
    assert "trusted_registry_reader" in source
