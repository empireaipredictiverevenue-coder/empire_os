"""Tests for the MX validator (no-API-key email validation)."""
import socket
from unittest.mock import patch, MagicMock

import pytest
from empire_os.mx_validator import (
    MxValidator, MxValidationResult,
    DISPOSABLE_DOMAINS, ROLE_PREFIXES,
    extract_emails_from_text, extract_phones_from_text,
)


class TestConstants:
    def test_disposable_blocklist_populated(self):
        assert "mailinator.com" in DISPOSABLE_DOMAINS
        assert "guerrillamail.com" in DISPOSABLE_DOMAINS
        assert len(DISPOSABLE_DOMAINS) > 10

    def test_role_prefixes_populated(self):
        assert "info" in ROLE_PREFIXES
        assert "noreply" in ROLE_PREFIXES
        assert "admin" in ROLE_PREFIXES


class TestValidator:
    def test_invalid_format(self):
        v = MxValidator(do_smtp_probe=False)
        r = v.validate("not-an-email")
        assert r.is_valid is False
        assert "format" in r.error

    def test_disposable_domain_blocked(self):
        v = MxValidator(do_smtp_probe=False)
        r = v.validate("foo@mailinator.com")
        assert r.is_valid is False
        assert r.is_disposable is True
        assert "disposable" in r.error

    def test_role_address_blocked(self):
        v = MxValidator(do_smtp_probe=False)
        r = v.validate("info@example.com")
        assert r.is_valid is False
        assert r.is_role_address is True

    def test_no_mx_record(self):
        v = MxValidator(do_smtp_probe=False)
        # TLD .invalid never has MX
        r = v.validate("foo@nonexistent-domain-12345.invalid")
        assert r.is_valid is False
        assert r.has_mx is False

    def test_valid_email_with_mx(self):
        """Email with a real MX record passes (gmail.com)."""
        v = MxValidator(do_smtp_probe=False)  # skip SMTP probe for test
        r = v.validate("test@gmail.com")
        # gmail has MX; should pass format + MX checks
        assert r.has_mx is True
        # Without SMTP probe, valid is True
        assert r.is_valid is True
        assert r.confidence >= 0.7

    def test_validator_chains_checks(self):
        v = MxValidator(do_smtp_probe=False)
        r = v.validate("test@gmail.com")
        assert "format:ok" in r.checks
        assert any("mx:" in c for c in r.checks)


class TestExtractors:
    def test_extract_emails(self):
        text = "Contact us at info@example.com or sales@acme.co.uk"
        emails = extract_emails_from_text(text)
        assert "info@example.com" in emails
        assert "sales@acme.co.uk" in emails

    def test_extract_emails_dedup(self):
        text = "a@b.com a@b.com c@d.com"
        emails = extract_emails_from_text(text)
        assert emails.count("a@b.com") == 1

    def test_extract_phones_us(self):
        text = "Call us at (555) 123-4567 or 555.123.4567"
        phones = extract_phones_from_text(text)
        assert len(phones) >= 2

    def test_extract_phones_intl(self):
        text = "International: +44 2079460958"
        phones = extract_phones_from_text(text)
        assert len(phones) >= 1

    def test_extract_from_empty(self):
        assert extract_emails_from_text("") == []
        assert extract_phones_from_text("") == []

def test_mx_lookup_returns_host_strings_in_preference_order(monkeypatch):
    class Exchange:
        def __init__(self, value):
            self.value = value

        def to_text(self):
            return self.value

    class Record:
        def __init__(self, host, preference):
            self.exchange = Exchange(host)
            self.preference = preference

    monkeypatch.setattr(
        "dns.resolver.Resolver.resolve",
        lambda self, domain, record_type: [
            Record("mx2.example.com.", 20),
            Record("mx1.example.com.", 10),
        ],
    )

    hosts = MxValidator(do_smtp_probe=False)._mx_lookup(
        "example.com"
    )

    assert hosts == ["mx1.example.com", "mx2.example.com"]

def test_smtp_probe_unavailable_is_not_misreported_as_recipient_rejection(monkeypatch):
    v = MxValidator(do_smtp_probe=True)
    monkeypatch.setattr(v, "_mx_lookup", lambda _domain: ["mx.example.com"])
    monkeypatch.setattr(
        v,
        "_smtp_probe",
        lambda _host, _email: ("unavailable", None, "TimeoutError"),
    )

    r = v.validate("person@example.com")

    assert r.is_valid is True
    assert r.has_mx is True
    assert r.smtp_accepts is False
    assert r.smtp_status == "unavailable"
    assert r.smtp_code is None
    assert r.confidence == 0.75
    assert r.error == "smtp probe unavailable"
    assert "smtp:unavailable" in r.checks
    assert not any(check.startswith("smtp:reject") for check in r.checks)


def test_explicit_smtp_5xx_rejection_fails_address(monkeypatch):
    v = MxValidator(do_smtp_probe=True)
    monkeypatch.setattr(v, "_mx_lookup", lambda _domain: ["mx.example.com"])
    monkeypatch.setattr(
        v,
        "_smtp_probe",
        lambda _host, _email: ("rejected", 550, "5.1.1 user unknown"),
    )

    r = v.validate("person@example.com")

    assert r.is_valid is False
    assert r.smtp_status == "rejected"
    assert r.smtp_code == 550
    assert r.smtp_accepts is False
    assert r.confidence == 0.5
    assert r.error == "smtp rejected"
    assert "smtp:reject:550" in r.checks


def test_smtp_temporary_reject_stays_inconclusive_not_invalid(monkeypatch):
    v = MxValidator(do_smtp_probe=True)
    monkeypatch.setattr(v, "_mx_lookup", lambda _domain: ["mx.example.com"])
    monkeypatch.setattr(
        v,
        "_smtp_probe",
        lambda _host, _email: ("temporary_reject", 451, "try again later"),
    )

    r = v.validate("person@example.com")

    assert r.is_valid is True
    assert r.smtp_status == "temporary_reject"
    assert r.smtp_code == 451
    assert r.smtp_accepts is False
    assert r.confidence == 0.70
    assert r.error == "smtp temporarily rejected"
    assert "smtp:temporary:451" in r.checks


def test_smtp_acceptance_raises_confidence(monkeypatch):
    v = MxValidator(do_smtp_probe=True)
    monkeypatch.setattr(v, "_mx_lookup", lambda _domain: ["mx.example.com"])
    monkeypatch.setattr(
        v,
        "_smtp_probe",
        lambda _host, _email: ("accepted", 250, "ok"),
    )

    r = v.validate("person@example.com")

    assert r.is_valid is True
    assert r.smtp_status == "accepted"
    assert r.smtp_code == 250
    assert r.smtp_accepts is True
    assert r.confidence == 0.95
    assert r.error == ""
    assert "smtp:accept:250" in r.checks

