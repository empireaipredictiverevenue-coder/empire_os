"""Offline invariants for the read-only direct USDT verifier catalog inspector."""
from scripts.inspect_direct_bsc_verifier_readiness import (
    APP, DB, GROUP, LOGIN, REVIEW, VERIFY,
    classify, first_matching_scram, main,
)
from empire_os.bsc_payment_operator_readiness import (
    LOGIN_FLAGS, PERMISSION_ROLE_FLAGS,
)


def good():
    return {
        "canonical": True,
        "roles": {
            GROUP: PERMISSION_ROLE_FLAGS,
            LOGIN: LOGIN_FLAGS,
            APP: (True, True, False, False, False, False, False),
        },
        "memberships": [(GROUP, LOGIN, False, True, False)],
        "privileges": {
            ("group", REVIEW): True,
            ("group", VERIFY): True,
            ("app", VERIFY): False,
            ("app", "public.approve_bsc_payment_request(uuid,text,text)"): False,
        },
        "database_privileges": (True, False, False),
        "hba": [{
            "rule_number": 1, "type": "local", "database": [DB],
            "user_name": [LOGIN], "auth_method": "scram-sha-256",
            "error": None,
        }],
    }


def test_ready_never_turns_checkout_on():
    output = classify(good())
    assert output["status"] == "DIRECT_VERIFIER_CATALOG_READY_AUTHENTICATION_TEST_REQUIRED"
    assert output["checkout_activated"] is False
    assert output["password_authentication_independently_verified"] is False
    assert output["payment_or_database_mutation"] is False


def test_missing_login_is_held_for_provisioning():
    data = good()
    del data["roles"][LOGIN]
    data["memberships"] = []
    data["database_privileges"] = None
    assert classify(data)["status"] == "DIRECT_VERIFIER_LOGIN_NOT_PROVISIONED"


def test_partial_or_unsafe_login_never_ready():
    for key, new in (
        ("database_privileges", (False, False, False)),
        ("database_privileges", (True, True, False)),
        ("database_privileges", (True, False, True)),
        ("memberships", [(GROUP, LOGIN, True, True, False)]),
        ("memberships", [(GROUP, LOGIN, False, True, True)]),
        ("memberships", [(GROUP, LOGIN, False, True, False),
                          ("empire_payment_approver", LOGIN, False, True, False)]),
    ):
        data = good()
        data[key] = new
        assert classify(data)["status"] == "BLOCKED_DIRECT_VERIFIER_LOGIN_OR_ACL"


def test_unexpected_admin_attributes_fail_closed():
    data = good()
    data["roles"][LOGIN] = (True, False, False, True, False, False, False)
    assert classify(data)["status"] == "BLOCKED_DIRECT_VERIFIER_LOGIN_OR_ACL"


def test_app_verification_grant_or_missing_function_fails():
    for key, value in (
        (("app", VERIFY), True),
        (("group", REVIEW), False),
        (("group", VERIFY), False),
    ):
        data = good()
        data["privileges"][key] = value
        assert classify(data)["status"] == "BLOCKED_DIRECT_VERIFIER_BASE_AUTHORITY"


def test_wrong_database_fails_closed():
    data = good()
    data["canonical"] = False
    assert classify(data)["status"] == "BLOCKED_DIRECT_VERIFIER_BASE_AUTHORITY"


def test_hba_shadowed_by_peer_or_trust_denies_even_if_later_scram():
    data = good()
    data["hba"].insert(0, {
        "rule_number": 0, "type": "local",
        "database": ["all"], "user_name": ["all"],
        "auth_method": "peer", "error": None,
    })
    assert not first_matching_scram(data["hba"])
    assert classify(data)["status"] == "BLOCKED_DIRECT_VERIFIER_LOGIN_OR_ACL"


def test_malformed_or_unparsed_hba_denied():
    data = good()
    data["hba"][0]["error"] = "invalid auth"
    assert classify(data)["status"] == "BLOCKED_DIRECT_VERIFIER_LOGIN_OR_ACL"


def test_invocation_rejects_writes_and_other_flags(capsys):
    assert main(["--apply"]) == 3
    assert "HELD_POSTGRES_READONLY_INVOCATION_REQUIRED" in capsys.readouterr().out

def test_staged_direct_config_never_activates_orders_or_payments():
    from pathlib import Path
    cfg = (Path(__file__).resolve().parents[1] /
           "deploy/systemd/30-direct-bsc-readonly.conf").read_text()
    assert 'Environment="EMPIRE_SELF_SERVE_SETTLEMENT_MODE=direct"' in cfg
    assert 'Environment="BSC_MIN_CONFIRMATIONS=12"' in cfg
    assert 'Environment="BSC_RPC_URL=https://bsc-dataseed.bnbchain.org"' in cfg
    assert 'Environment="BSC_TREASURY_ADDRESS=0x1339b487046B0ad924a10c20b1791608EA8595a8"' in cfg
    assert 'Environment="EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=OFF"' in cfg
    assert 'Environment="EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=OFF"' in cfg
    assert "ON" not in cfg.split("AUTHORIZED=")[-1]
