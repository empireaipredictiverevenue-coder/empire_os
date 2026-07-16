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