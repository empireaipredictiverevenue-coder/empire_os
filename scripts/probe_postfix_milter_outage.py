"""Explicit offline Postfix Milter-outage test; never contacts a real mailbox.

Running the probe requires an independently verified network-disabled
disposable container with the specific one-alias staging profile installed.
Without a verifier on 127.0.0.1:11332, Postfix MUST temporarily refuse
the SMTP transaction rather than deliver unverified mail.

Only the synthetic fixture is used; no live buyer, MX, payment or CRM.
"""
from __future__ import annotations

import argparse
from email.message import EmailMessage
from email.policy import SMTP as SMTP_POLICY
import json
import smtplib
from typing import Any, Callable

from scripts.probe_postfix_staging_smtp_rcpt import (
    BannerCapturingSMTP, HOST, ALLOWED_RCPT,
)


def probe_milter_failure(
    factory: Callable[..., Any] = BannerCapturingSMTP,
) -> dict[str, object]:
    receipt = {
        "schema_version": "empire.mail.milter_unavailable_tempfail.v1",
        "mode": "ISOLATED_SYNTHETIC_ONLY",
        "status": "HOLD_MILTER_FAIL_CLOSED_UNVERIFIED",
        "milter_unavailable_tempfailed": False,
        "smtp_data_accepted": False,
        "authenticated_sender_proven": False,
        "production_mail_received": False,
        "mx_changed": False,
    }
    fixture=EmailMessage()
    fixture["Message-ID"]="<offline-milter-down@offline.invalid>"
    fixture["From"]="untrusted@offline.invalid"
    fixture["To"]=ALLOWED_RCPT
    fixture.set_content("EMPIRE_MILTER_OUTAGE_SYNTHETIC_ONLY")
    wire=fixture.as_bytes(policy=SMTP_POLICY)
    if len(wire)>1024:
        return receipt
    try:
        with factory("127.0.0.1",2525,timeout=4) as client:
            banner=getattr(client,"welcome",b"")
            if not isinstance(banner,bytes) or HOST.encode() not in banner:
                return receipt
            if client.ehlo("offline.invalid")[0] != 250:
                return receipt
            steps=[
                lambda:client.mail("untrusted@offline.invalid"),
                lambda:client.rcpt(ALLOWED_RCPT),
                lambda:client.data(wire),
            ]
            for step in steps:
                try:
                    code, _=step()
                except smtplib.SMTPResponseException as reply:
                    code=reply.smtp_code
                if 400 <= code < 500:
                    return {**receipt,
                        "status": "MILTER_UNAVAILABLE_TEMPFAIL_VERIFIED",
                        "milter_unavailable_tempfailed": True,
                        "smtp_reply_code": code,
                    }
                if code != 250 and code != 251 and code != 354:
                    return {**receipt,"smtp_reply_code":code}
            # A completely accepted SMTP DATA is an explicit failure.
            return {**receipt,
                "status":"HOLD_UNAUTHENTICATED_MESSAGE_ACCEPTED",
                "smtp_data_accepted": True,
            }
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        return {**receipt,"error_type":type(exc).__name__}


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--approved-offline-milter-outage",action="store_true")
    opts=parser.parse_args(argv)
    if not opts.approved_offline_milter_outage:
        print(json.dumps({
            "status":"MILTER_OUTAGE_PROBE_NOT_REQUESTED",
            "network_calls":0,"smtp_data_accepted":False,
            "mx_changed":False
        },sort_keys=True))
        return 0
    result=probe_milter_failure()
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="MILTER_UNAVAILABLE_TEMPFAIL_VERIFIED" else 2


if __name__=="__main__":
    raise SystemExit(main())
