"""Postfix missing-identity preflight is read-only and always fail-closed."""
import json
import pytest
from empire_os.owned_postfix_receiver_preflight import (
    assess_postfix_receiver_prerequisites as assess,
)
from scripts import probe_owned_postfix_receiver_prerequisites as operator

BINS={"postfix":False,"postconf":False,"postmap":False}
NOBODY={"uid":65534,"gid":65534}
MAIL={"uid":101,"gid":102}
DROP={"uid":0,"gid":103}


def review(**overrides):
    config={
        "binaries": BINS,
        "mail_owner":None,
        "postdrop":None,
        "default_privs":NOBODY,
        "isolated_runtime_available":None,
    }
    config.update(overrides)
    return assess(**config)


def test_no_installed_mta_explicitly_blocks_release():
    output=review()
    assert output["status"]=="HOLD_POSTFIX_RECEIVER_ACTIVATION"
    assert "POSTFIX_BINARIES_NOT_INSTALLED" in output["blocked_reasons"]
    assert "UNPRIVILEGED_POSTFIX_MAIL_OWNER_MISSING" in output["blocked_reasons"]
    assert "POSTDROP_SETGID_GROUP_MISSING" in output["blocked_reasons"]
    assert "ISOLATED_SMTP_RUNTIME_NOT_PROVEN" in output["blocked_reasons"]
    assert output["smtp_rcpt_acceptance_verified"] is False
    assert output["external_relay_denial_verified"] is False
    assert output["real_buyer_replies_verified"] is None
    assert output["execution_authority"]=="none"
    assert output["mail_sent"] is False
    assert output["mail_received"] is False
    assert output["dns_changed"] is False
    assert output["services_changed"] is False
    assert output["system_packages_changed"] is False


def test_even_complete_inventory_does_not_fake_smtp_acceptance():
    outcome=review(
        binaries={key:True for key in BINS},
        mail_owner=MAIL,postdrop=DROP,default_privs=NOBODY,
        isolated_runtime_available=True,
    )
    assert outcome["status"]=="HOLD_POSTFIX_RECEIVER_ACTIVATION"
    assert outcome["smtp_rcpt_acceptance_verified"] is False
    assert outcome["external_relay_denial_verified"] is False
    assert outcome["original_message_authentication_verified"] is False
    assert outcome["blocked_reasons"]==[
        "EXISTING_MX_CUTOVER_UNAPPROVED",
        "FIRST_PARTY_INGRESS_CUSTODY_UNVERIFIED",
        "LIVE_SMTP_ACCEPTANCE_UNTESTED",
        "MAIL_TRANSPORT_AUTHENTICATION_UNAUDITED",
    ]


@pytest.mark.parametrize("bad",[
    {"binaries":{"postfix":True}},
    {"binaries":{"postfix":1,"postmap":True,"postconf":True}},
    {"mail_owner":{"uid":1000,"gid":"1000"}},
    {"postdrop":{"uid":0}},
    {"default_privs":{"uid":-1,"gid":65534}},
    {"isolated_runtime_available":"yes"},
])
def test_untrusted_process_metadata_fails(bad):
    with pytest.raises(ValueError):
        review(**bad)


def test_conflicting_postfix_privilege_groups_cannot_grant_release():
    a=review(
        binaries={key:True for key in BINS},
        mail_owner={"uid":101,"gid":103},postdrop=DROP,default_privs=NOBODY,
    )
    assert "MAIL_OWNER_AND_POSTDROP_GROUP_CONFLICT" in a["blocked_reasons"]
    b=review(
        binaries={key:True for key in BINS},
        mail_owner=MAIL,
        postdrop={"uid":0,"gid":65534},default_privs=NOBODY,
    )
    assert "DEFAULT_PRIVS_AND_POSTDROP_GROUP_CONFLICT" in b["blocked_reasons"]


def test_probe_default_cannot_inspect_host(monkeypatch,capsys):
    monkeypatch.setattr(operator,"inspect_preflight",
        lambda: pytest.fail("no implicit environment inspection"))
    assert operator.main([])==0
    data=json.loads(capsys.readouterr().out)
    assert data["status"]=="RECEIVER_PREFLIGHT_NOT_REQUESTED"
    assert data["execution_authority"]=="none"


def test_probe_readonly_returns_nonzero_held_status(monkeypatch,capsys):
    monkeypatch.setattr(operator,"inspect_preflight",lambda:review())
    assert operator.main(["--read-only"])==2
    data=json.loads(capsys.readouterr().out)
    assert data["status"]=="HOLD_POSTFIX_RECEIVER_ACTIVATION"
    assert data["mail_sent"] is False
    assert data["services_changed"] is False
