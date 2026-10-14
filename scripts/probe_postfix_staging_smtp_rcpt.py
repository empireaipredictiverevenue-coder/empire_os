"""Wave 15 operator-controlled loopback SMTP RCPT admission probe.

Never sends DATA, delivers mail, changes DNS, installs packages or touches
production mail. Requires explicit operator invocation after confirming an
ISOLATED staging Postfix daemon is listening on 127.0.0.1:2525.
Untrusted or unexpected SMTP greeting => no MAIL/RCPT attempted.

This validates SMTP *recipient admission*, not original-message provenance,
SPF/DKIM/DMARC, durable delivery, signed receipts or production readiness.
"""
from __future__ import annotations

import argparse
import json
import smtplib
from typing import Callable, Any
from uuid import UUID

from empire_os.owned_postfix_staging_profile import DOMAIN, HOST

PORT = 2525
LOOPBACK = "127.0.0.1"
TEST_INTENT = str(UUID(int=121))
ALLOWED_RCPT = f"reply+{TEST_INTENT}@{DOMAIN}"
CASES = (
    ("explicit_fixture_alias", ALLOWED_RCPT, True),
    ("bare_reply", f"reply@{DOMAIN}", False),
    ("other_reply_alias", f"reply+{str(UUID(int=122))}@{DOMAIN}", False),
    ("unlisted_mailbox", f"unknown@{DOMAIN}", False),
    ("external_relay", "anyone@external.invalid", False),
)


def probe_rcpt(
    *, factory: Callable[..., Any] = smtplib.SMTP,
) -> dict[str, object]:
    observations: list[dict[str, object]] = []
    try:
        with factory(LOOPBACK, PORT, timeout=4) as client:
            banner = getattr(client, "welcome", b"")
            banner_text = (
                banner.decode("ascii", "ignore")
                if isinstance(banner, bytes) else str(banner)
            )
            if HOST not in banner_text or "ESMTP" not in banner_text.upper():
                raise ValueError("unrecognized isolated Postfix SMTP banner")
            code, reply = client.ehlo("empire-offline-fixture.invalid")
            if code != 250:
                raise ValueError("staging SMTP EHLO failed")
            features = getattr(client, "esmtp_features", {})
            if not isinstance(features, dict) or any(
                item in features for item in ("auth", "starttls")
            ):
                raise ValueError("unexpected public SMTP feature in offline profile")
            for label, recipient, expected in CASES:
                mail_code, _ = client.mail("stage-probe@fixture.invalid")
                if mail_code != 250:
                    raise ValueError("test sender admission failed")
                rcpt_code, _ = client.rcpt(recipient)
                accepted = rcpt_code in (250, 251)
                observations.append({
                    "test_case": label,
                    "rcpt_code": rcpt_code,
                    "accepted": accepted,
                    "expected_accepted": expected,
                    "passed": accepted == expected and (
                        accepted or rcpt_code in (550, 551, 553, 554)
                    ),
                })
                # RSET prevents accumulation of recipients; never DATA.
                reset_code, _ = client.rset()
                if reset_code != 250:
                    raise ValueError("staging SMTP RSET failed")
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        return {
            "schema_version": "empire.mail.postfix_loopback_admission.v1",
            "status": "HOLD_STAGING_SMTP_UNAVAILABLE",
            "error_type": type(exc).__name__,
            "cases_evaluated": len(observations),
            "all_cases_passed": False,
            "actual_message_data_sent": False,
            "mail_delivered": False,
            "dns_modified": False,
            "execution_authority": "none",
        }
    succeeded = len(observations) == len(CASES) and all(
        row["passed"] is True for row in observations
    )
    return {
        "schema_version": "empire.mail.postfix_loopback_admission.v1",
        "status": (
            "LOOPBACK_RCPT_ADMISSION_VERIFIED"
            if succeeded else "HOLD_STAGING_RCPT_POLICY_MISMATCH"
        ),
        "isolated_test_only": True,
        "cases_evaluated": len(observations),
        "all_cases_passed": succeeded,
        "observations": observations,
        "smtpd_configuration_source_independently_audited": False,
        "actual_message_data_sent": False,
        "mail_delivered": False,
        "provider_authentication_verified": False,
        "ingress_receipt_verified": False,
        "customer_identity_verified": False,
        "production_mx_cutover_authorized": False,
        "dns_modified": False,
        "execution_authority": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage-only Postfix localhost RCPT admission, never DATA"
    )
    parser.add_argument("--approved-isolated-loopback-rcpt-test", action="store_true")
    args = parser.parse_args(argv)
    if not args.approved_isolated_loopback_rcpt_test:
        print(json.dumps({
            "schema_version": "empire.mail.postfix_loopback_admission.v1",
            "status": "EXPLICIT_ISOLATED_TEST_NOT_REQUESTED",
            "network_connections": 0,
            "actual_message_data_sent": False,
            "dns_modified": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 0
    packet = probe_rcpt()
    print(json.dumps(packet, sort_keys=True))
    return 0 if packet["status"] == "LOOPBACK_RCPT_ADMISSION_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
