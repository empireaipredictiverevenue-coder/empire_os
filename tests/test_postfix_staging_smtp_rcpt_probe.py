"""SMTP admission operator tests; synthetic transport only, never DATA."""
from __future__ import annotations

import json
import pytest

from scripts import probe_postfix_staging_smtp_rcpt as probe


class FakeIsolatedPostfix:
    def __init__(self, host, port, timeout):
        assert (host, port) == ("127.0.0.1", 2525)
        assert timeout <= 4
        self.welcome = b"220 mx-stage.mail.empire-ai.co.uk ESMTP Postfix (fixture)"
        self.esmtp_features = {"size": "524288", "8bitmime": ""}
        self.events = []
        self.altered = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.events.append("CLOSE")

    def ehlo(self, identity):
        self.events.append("EHLO")
        return 250, b"test"

    def mail(self, sender):
        self.events.append(("MAIL", sender))
        return 250, b"Sender ok"

    def rcpt(self, recipient):
        self.events.append(("RCPT", recipient))
        expected = recipient == probe.ALLOWED_RCPT
        return self.altered.get(recipient, 250 if expected else 550), b"test only"

    def rset(self):
        self.events.append("RSET")
        return 250, b"reset"

    def data(self, *args, **kwargs):
        raise AssertionError("no DATA should ever be sent")


def test_all_five_fixture_policy_rcpt_checks_no_data():
    made = []
    def factory(*args, **kwargs):
        obj = FakeIsolatedPostfix(*args, **kwargs)
        made.append(obj)
        return obj
    packet = probe.probe_rcpt(factory=factory)
    assert packet["status"] == "LOOPBACK_RCPT_ADMISSION_VERIFIED"
    assert packet["all_cases_passed"] is True
    assert packet["cases_evaluated"] == 5
    assert [row["accepted"] for row in packet["observations"]] == [
        True, False, False, False, False
    ]
    assert len([e for e in made[0].events if e == "RSET"]) == 5
    assert len([e for e in made[0].events if isinstance(e, tuple) and e[0] == "RCPT"]) == 5
    assert packet["mail_delivered"] is False
    assert packet["actual_message_data_sent"] is False
    assert packet["ingress_receipt_verified"] is False
    assert packet["customer_identity_verified"] is False
    assert packet["production_mx_cutover_authorized"] is False


def test_unapproved_default_does_not_create_network_socket(monkeypatch, capsys):
    monkeypatch.setattr(probe, "probe_rcpt",
        lambda: pytest.fail("default MUST NOT open SMTP"))
    assert probe.main([]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["network_connections"] == 0
    assert status["status"] == "EXPLICIT_ISOLATED_TEST_NOT_REQUESTED"


def test_explicit_operator_flag_returns_success_only_if_all_cases_pass(monkeypatch, capsys):
    original = probe.probe_rcpt
    monkeypatch.setattr(probe, "probe_rcpt", lambda: original(factory=FakeIsolatedPostfix))
    assert probe.main(["--approved-isolated-loopback-rcpt-test"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "LOOPBACK_RCPT_ADMISSION_VERIFIED"


@pytest.mark.parametrize("special, code", [
    ("external_relay", 250),
    ("bare_reply", 250),
    ("other_reply_alias", 251),
    ("explicit_fixture_alias", 550),
    ("unlisted_mailbox", 450),
])
def test_policy_mismatch_or_temporary_fail_never_claims_success(special, code):
    class Broken(FakeIsolatedPostfix):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            recipient = next(v for n, v, _ in probe.CASES if n == special)
            self.altered[recipient] = code
    packet = probe.probe_rcpt(factory=Broken)
    assert packet["status"] == "HOLD_STAGING_RCPT_POLICY_MISMATCH"
    assert packet["all_cases_passed"] is False
    assert packet["mail_delivered"] is False


def test_non_matching_staging_banner_fails_before_mail_or_rcpt():
    made = []
    class Untrusted(FakeIsolatedPostfix):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.welcome = b"220 unknown.example ESMTP provider"
            made.append(self)
    packet = probe.probe_rcpt(factory=Untrusted)
    assert packet["status"] == "HOLD_STAGING_SMTP_UNAVAILABLE"
    assert made[0].events == ["CLOSE"]


@pytest.mark.parametrize("advertised", [{"auth": "PLAIN"}, {"starttls": ""}])
def test_auth_or_starttls_advertisement_abstains_without_recipient_commands(advertised):
    made=[]
    class Unsafe(FakeIsolatedPostfix):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.esmtp_features = advertised
            made.append(self)
    packet=probe.probe_rcpt(factory=Unsafe)
    assert packet["status"]=="HOLD_STAGING_SMTP_UNAVAILABLE"
    assert not any(isinstance(x,tuple) for x in made[0].events)


def test_unavailable_smtp_fails_closed_with_no_secrets():
    def fail(*_args, **_kwargs):
        raise ConnectionRefusedError("refused")
    packet=probe.probe_rcpt(factory=fail)
    assert packet["status"]=="HOLD_STAGING_SMTP_UNAVAILABLE"
    assert packet["cases_evaluated"]==0
    assert packet["execution_authority"]=="none"


def test_smtp_result_does_not_embed_any_address_or_message_body():
    result = probe.probe_rcpt(factory=FakeIsolatedPostfix)
    text = json.dumps(result)
    assert "mail.empire-ai.co.uk" not in text
    assert "stage-probe" not in text
    assert "DATA" not in text
