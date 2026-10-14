"""Postfix receive-only staging profile: deny-by-default static assertions.

This is deliberately an offline *candidate configuration* test suite.
Without a real postconf/postmap/Postfix, acceptance and relay behaviour
must still be tested in an independently contained MTA before deployment.
"""
from pathlib import Path
from uuid import UUID
import pytest

from empire_os.owned_postfix_staging_profile import (
    DOMAIN, StageIdentity, generate_candidate_postfix_profile,
    validate_candidate_postfix_profile,
)
from empire_os.owned_ingress_receipt_producer import ALIAS

INTENT = str(UUID(int=121))
SPEC = StageIdentity(intent_id=INTENT, uid=15000, gid=15000)
ROOT = Path("/tmp/empire-postfix-stage-fixture123")


def generated():
    return generate_candidate_postfix_profile(SPEC, root=ROOT)


def test_one_exact_recipient_and_no_open_relay_or_catchall():
    files = generated()
    report = validate_candidate_postfix_profile(files, identity=SPEC, root=ROOT)
    assert report["mode"] == "OFFLINE"
    assert report["allowed_recipients"] == 1
    assert report["listen_address"] == "127.0.0.1:2525"
    assert report["bare_reply_mailbox_admitted"] is False
    assert report["wildcard_or_catchall_admitted"] is False
    assert report["external_relay_enabled"] is False
    assert report["receiver_deployed"] is False
    assert report["actual_mail_received"] is False
    assert report["runtime_postfix_parser_verified"] is False
    assert report["postmap_compiled"] is False
    assert report["mx_changed"] is False
    assert report["mail_sent"] is False
    assert report["execution_authority"] == "none"
    assert files["recipients"] == f"reply+{INTENT}@{DOMAIN} jev-{INTENT}/\n"
    assert ALIAS.fullmatch(files["recipients"].split()[0])
    assert f"reply@{DOMAIN}" not in files["recipients"]
    assert not files["recipients"].split()[0].startswith("@")
    assert "reject_unauth_destination" in files["main.cf"]
    assert "reject_unlisted_recipient" in files["main.cf"]
    assert "virtual_alias_domains = \n" in files["main.cf"]
    assert "relay_domains = \n" in files["main.cf"]


def test_staging_profile_deterministic_with_no_secrets():
    first = generated()
    second = generated()
    assert first == second
    outcome = validate_candidate_postfix_profile(first, identity=SPEC, root=ROOT)
    assert len(outcome["config_sha256"]) == 64
    for value in first.values():
        assert "private_key" not in value
        assert "password" not in value
        assert "smtp.google" not in value
        assert "inbound-smtp." not in value


@pytest.mark.parametrize("find,replace", [
    ("inet_interfaces = loopback-only", "inet_interfaces = all"),
    ("inet_protocols = ipv4", "inet_protocols = all"),
    ("relay_domains = \n", "relay_domains = all\n"),
    ("smtpd_sasl_auth_enable = no", "smtpd_sasl_auth_enable = yes"),
    ("reject_unauth_destination", "permit_mynetworks"),
    ("virtual_mailbox_domains = mail.empire-ai.co.uk",
     "virtual_mailbox_domains = empire-ai.co.uk"),
    ("mydestination = localhost", "mydestination = mail.empire-ai.co.uk"),
    ("virtual_alias_domains = \n", "virtual_alias_domains = mail.empire-ai.co.uk\n"),
    ("message_size_limit = 524288", "message_size_limit = 100000000"),
    ("virtual_uid_maps = static:15000", "virtual_uid_maps = static:0"),
    ("mynetworks = 127.0.0.0/8", "mynetworks = 0.0.0.0/0"),
    ("recipient_delimiter = +", "recipient_delimiter = -"),
])
def test_unsafe_main_cf_mutations_are_rejected(find, replace):
    data = generated()
    assert find in data["main.cf"]
    data["main.cf"] = data["main.cf"].replace(find, replace)
    with pytest.raises(ValueError, match="deny-by-default"):
        validate_candidate_postfix_profile(data, identity=SPEC, root=ROOT)


@pytest.mark.parametrize("mutated", [
    "smtp inet n - n - - smtpd\n",
    "0.0.0.0:25 inet n - n - - smtpd\n",
    "submission inet n - n - - smtpd\n",
    "127.0.0.1:587 inet n - n - - smtpd\n",
    "smtp unix - - n - - smtp\n",
])
def test_added_listener_or_outbound_transport_denied(mutated):
    data = generated()
    data["master.cf"] += mutated
    with pytest.raises(ValueError, match="listener"):
        validate_candidate_postfix_profile(data, identity=SPEC, root=ROOT)


@pytest.mark.parametrize("alter", [
    f"@{DOMAIN} jev-catchall/\n",
    f"reply@{DOMAIN} jev-bare/\n",
    f"reply+{str(UUID(int=99))}@{DOMAIN} jev-unknown/\n",
    f"reply+{INTENT}@{DOMAIN} jev-{INTENT}/\n"
    + f"reply+{str(UUID(int=122))}@{DOMAIN} jev-other/\n",
    f"reply+{INTENT}@{DOMAIN} ../../../unsafe/\n",
])
def test_catch_all_extra_or_unlisted_address_denied(alter):
    data = generated()
    data["recipients"] = alter
    with pytest.raises(ValueError, match="one exact"):
        validate_candidate_postfix_profile(data, identity=SPEC, root=ROOT)


@pytest.mark.parametrize("path", [
    Path("/etc/postfix"),
    Path("/srv/empire_os"),
    Path("/tmp"),
    Path("/tmp/empire-postfix-stage-ok/../../etc"),
    Path("/home/ubuntu/empire-postfix-stage-fixture"),
    Path("relative/tmp"),
])
def test_production_or_uncontrolled_paths_refused(path):
    with pytest.raises(ValueError):
        generate_candidate_postfix_profile(SPEC, root=path)


@pytest.mark.parametrize("uid,gid", [(0,15000), (15000,0), (True,15000), (15000,"15000"), (999,15000), (15000,999)])
def test_unprivileged_maildir_owner_required(uid,gid):
    with pytest.raises(ValueError, match="unprivileged"):
        generate_candidate_postfix_profile(
            StageIdentity(INTENT, uid, gid), root=ROOT
        )


def test_uppercase_or_malformed_intent_cannot_enter_recipient_maps():
    for candidate in ("00000000-0000-0000-0000-000000000ABC", "not-a-uuid", "", str(UUID(int=122))+"\n"):
        with pytest.raises(ValueError):
            generate_candidate_postfix_profile(
                StageIdentity(candidate,15000,15000), root=ROOT
            )


def test_unknown_config_keys_or_missing_files_denied():
    data = generated()
    data["main.cf"] += "permit_mynetworks = yes\n"
    with pytest.raises(ValueError):
        validate_candidate_postfix_profile(data,identity=SPEC,root=ROOT)
    data = generated()
    del data["master.cf"]
    with pytest.raises(ValueError):
        validate_candidate_postfix_profile(data,identity=SPEC,root=ROOT)


def test_profile_cannot_be_read_as_a_live_jev_ingress_release():
    from empire_os.jev_gtm_mail_source_truth import assess_jev_ingress_truth
    result = assess_jev_ingress_truth(
        relay_health=None,
        founder_readiness=None,
        inbound_health=None,
        root_mx=[], reply_mx=[],
        canonical_release_dropin_present=False,
        canonical_reader_credential_present=False,
    )
    assert result["status"] == "HOLD_FIRST_PARTY_REPLY_ACTIVATION"
    assert result["first_party_inbound_transport_verified"] is False
    assert result["independently_verified_buyer_replies"] is None
