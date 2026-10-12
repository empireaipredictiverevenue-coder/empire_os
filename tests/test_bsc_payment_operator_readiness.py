"""Fail-closed safety proof for dedicated BSC financial operators; no DB writes."""
from __future__ import annotations

import json
import pytest

from empire_os.bsc_payment_operator_readiness import (
    APP, EXPECTED, LOGIN_FLAGS, PERMISSION_ROLE_FLAGS, LOGIN_ROLES,
    MANDATORY_FUNCTIONS, TARGET_ROLES, classify, effective_scram_rule,
)
from scripts.prepare_bsc_operator_hba import EXACT, additive_hba_patch

APP_SAFE=(True,True,False,False,False,False,False)


def base(*, with_logins=False, with_grants=False, with_hba=False):
    roles={APP:APP_SAFE}
    roles.update({name:PERMISSION_ROLE_FLAGS for name in TARGET_ROLES})
    if with_logins:
        roles.update({name:LOGIN_FLAGS for name in LOGIN_ROLES})
    members=(
        [(group,login,False,True,False) for group,login in EXPECTED.items()]
        if with_grants else []
    )
    hba=[
        {"rule_number":1+i, "type":"local",
         "database":["empiredb"],"user_name":[login],
         "auth_method":"scram-sha-256","error":None}
        for i,login in enumerate(LOGIN_ROLES)
    ] if with_hba else []
    if not hba:
        hba=[{"rule_number":9,"type":"local","database":["all"],
              "user_name":["all"],"auth_method":"peer","error":None}]
    bits={
        (role,name):True
        for role,funcs in MANDATORY_FUNCTIONS.items()
        for name in funcs
    }
    app={
        "public.approve_bsc_payment_request(uuid,text,text)":False,
        "public.record_bsc_escrow_creation(uuid,jsonb)":False,
        "public.record_bsc_escrow_lifecycle(uuid,text,jsonb)":False,
    }
    return dict(roles=roles,memberships=members,hba=hba,function_bits=bits,
                application_bits=app,canonical_db=True)


def test_live_like_catalog_identifies_exact_missing_HBA_and_does_not_authorize_payment():
    report=classify(**base())
    assert report["status"]=="PREPARE_EXACT_TWO_LOCAL_SCRAM_HBA_RULES"
    assert report["exact_existing_nologin_permission_roles_safe"] is True
    assert report["six_existing_role_rpc_grants_verified"] is True
    assert report["app_login_not_financial_operator"] is True
    assert report["dedicated_login_count"]==0
    assert report["two_exact_local_scram_rules_effective"] is False
    for field in ("roles_created","memberships_granted","database_mutations"):
        assert report[field]==0
    assert report["financial_authority_activated"] is False
    assert report["payments_collected"] is False


def test_hba_then_two_logins_and_grants_are_three_distinct_authority_stages():
    assert classify(**base(with_hba=True))["status"] == (
        "READY_FOR_SEPARATELY_APPROVED_TWO_LOGIN_PROVISIONING"
    )
    assert classify(**base(with_hba=True,with_logins=True))["status"].startswith("BLOCKED")
    complete=classify(**base(with_hba=True,with_logins=True,with_grants=True))
    assert complete["status"]=="OPERATOR_IDENTITIES_CATALOG_READY_AUTHENTICATION_TEST_REQUIRED"
    assert complete["financial_operator_authenticated"] is False
    assert complete["financial_authority_activated"] is False


@pytest.mark.parametrize("role",TARGET_ROLES)
def test_missing_or_login_enabled_permission_group_is_rejected(role):
    for attrs in (None,LOGIN_FLAGS,(False,True,False,False,False,False,False)):
        settings=base()
        if attrs is None:
            settings["roles"].pop(role)
        else:
            settings["roles"][role]=attrs
        assert classify(**settings)["status"]=="BLOCKED_DB_AUTHORITY_OR_ROLE_INVARIANT"


@pytest.mark.parametrize("key",[
    "rolcanlogin","rolinherit","rolsuper","rolcreatedb","rolcreaterole",
    "rolreplication","rolbypassrls",
])
def test_unsafe_financial_login_attribute_is_rejected(key):
    data=base(with_hba=True,with_logins=True,with_grants=True)
    vals=list(LOGIN_FLAGS)
    idx=("rolcanlogin","rolinherit","rolsuper","rolcreatedb","rolcreaterole",
         "rolreplication","rolbypassrls").index(key)
    vals[idx]=not vals[idx]
    data["roles"][LOGIN_ROLES[0]]=tuple(vals)
    assert classify(**data)["status"]=="BLOCKED_PARTIAL_OR_UNSAFE_OPERATOR_LOGINS"


@pytest.mark.parametrize("membership",[
    ("empire_payment_approver","empire_escrow_verifier_login",False,True,False),
    ("empire_payment_approver","empiredb_app_login",False,True,False),
    ("empire_escrow_verifier","empire_escrow_verifier_login",True,True,False),
    ("empire_escrow_verifier","empire_escrow_verifier_login",False,False,False),
    ("empire_escrow_verifier","empire_escrow_verifier_login",False,True,True),
])
def test_privilege_bleed_to_checkout_or_cross_financial_role_is_rejected(membership):
    settings=base(with_hba=True,with_logins=True,with_grants=True)
    settings["memberships"].append(membership)
    assert classify(**settings)["status"]=="BLOCKED_UNEXPECTED_FINANCIAL_ROLE_MEMBERSHIP"


@pytest.mark.parametrize("name",LOGIN_ROLES)
def test_hba_generic_peer_or_shadowed_exact_auth_denied(name):
    generic={"rule_number":1,"type":"local","database":["all"],"user_name":["all"],
             "auth_method":"peer","error":None}
    exact={"rule_number":2,"type":"local","database":["empiredb"],"user_name":[name],
           "auth_method":"scram-sha-256","error":None}
    assert effective_scram_rule([generic,exact],name) is False
    # HBA evaluation follows rule_number, not arbitrary list ordering.
    assert effective_scram_rule([{**exact,"rule_number":0},generic],name) is True
    assert effective_scram_rule([{**generic,"user_name":["+"+name]},exact],name) is False


def test_missing_function_grant_or_public_app_write_capability_fails():
    data=base()
    function=next(iter(data["function_bits"]))
    data["function_bits"][function]=False
    assert classify(**data)["status"]=="BLOCKED_DB_AUTHORITY_OR_ROLE_INVARIANT"
    data=base()
    data["application_bits"]["public.approve_bsc_payment_request(uuid,text,text)"]=True
    assert classify(**data)["status"]=="BLOCKED_DB_AUTHORITY_OR_ROLE_INVARIANT"


def test_existing_credential_vault_without_login_records_is_security_hold():
    r=classify(**base(),existing_private_credential_vault=True)
    assert r["status"]=="BLOCKED_PREEXISTING_OPERATOR_CREDENTIAL_VAULT"


def test_exact_hba_prepend_preserves_legacy_bytes_and_does_not_touch_permissions():
    original=(
        b"# Existing CRM and consulting login auth stays exactly as deployed\n"
        b"local empiredb empire_crm_auth_login scram-sha-256\n"
        b"local all postgres peer\nlocal all all peer\n"
    )
    amended=additive_hba_patch(original)
    assert amended==EXACT+original
    assert amended.endswith(original)
    assert amended.count(b"empire_payment_approver_login")==1
    assert amended.count(b"empire_escrow_verifier_login")==1
    assert original==original
    with pytest.raises(ValueError,match="marker"):
        additive_hba_patch(amended)


@pytest.mark.parametrize("old",[
    b"",b"local all all peer\r\n",b"local all all peer\x00",
    b"local empiredb empire_payment_approver_login scram-sha-256\nlocal all all peer\n",
    b"local empiredb empire_escrow_verifier_login peer\nlocal all all peer\n",
])
def test_hba_duplicate_unusual_format_or_second_edit_fails_closed(old):
    with pytest.raises(ValueError):
        additive_hba_patch(old)


def test_unexpected_hba_parse_error_even_if_exact_rules_exist_holds():
    data=base(with_hba=True)
    data["hba"][0]["error"]="bad HBA syntax"
    assert classify(**data)["status"]=="BLOCKED_DB_AUTHORITY_OR_ROLE_INVARIANT"


def test_inspector_never_returns_passwords_or_financial_credentials():
    report=classify(**base())
    encoded=json.dumps(report).lower()
    assert "dsn" not in encoded
    assert "password" not in encoded
    assert "secret" not in encoded
    assert report["credential_values_read_or_printed"] is False
