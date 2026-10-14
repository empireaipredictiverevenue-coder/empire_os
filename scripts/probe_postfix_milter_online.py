"""Explicit synthetic SMTP check with a live local Milter attached.

A working Milter is not an authenticated original-sender result: this test
proves Postfix receives a successful Milter response and can complete DATA.
With a network-disabled test container, no real external DNS authentication
or buyer identity can be established.
"""
from __future__ import annotations

import argparse
from email.message import EmailMessage
from email.policy import SMTP as SMTP_POLICY
import json
import smtplib
from typing import Callable, Any

from scripts.probe_postfix_staging_smtp_rcpt import (
    BannerCapturingSMTP, HOST, ALLOWED_RCPT,
)


def probe_milter_online(
    factory: Callable[..., Any] = BannerCapturingSMTP,
) -> dict[str, object]:
    report={
        "schema_version":"empire.mail.milter_online_synthetic_acceptance.v1",
        "mode":"ISOLATED_NETWORK_DISABLED",
        "status":"HOLD_MILTER_ONLINE_NOT_PROVEN",
        "authenticated_sender_proven":False,
        "spf_dkim_dmarc_pass_proven":False,
        "trusted_receipt_issued":False,
        "customer_mail_delivered":False,
        "production_mx_changed":False,
        "synthetic_smtp_data_accepted":False,
    }
    msg=EmailMessage()
    msg["Message-ID"]="<rspamd-online-synthetic@offline.invalid>"
    msg["From"]="synthetic-unverified@offline.invalid"
    msg["To"]=ALLOWED_RCPT
    msg.set_content("EMPIRE_LOCAL_MILTER_ONLINE_SYNTHETIC_NO_REAL_SENDER")
    payload=msg.as_bytes(policy=SMTP_POLICY)
    if len(payload)>1024:return report
    try:
        with factory("127.0.0.1",2525,timeout=12) as smtp:
            banner=getattr(smtp,"welcome",b"")
            if not isinstance(banner,bytes) or HOST.encode() not in banner:return report
            if smtp.ehlo("offline.invalid")[0] != 250:return report
            if smtp.mail("synthetic-unverified@offline.invalid")[0] != 250:return report
            if smtp.rcpt(ALLOWED_RCPT)[0] not in (250,251):return report
            code,_=smtp.data(payload)
            if code != 250:return {**report,"smtp_code":code}
            return {**report,
                "status":"MILTER_ONLINE_SYNTHETIC_DATA_ACCEPTED",
                "synthetic_smtp_data_accepted":True,
                "smtp_code":code,
            }
    except smtplib.SMTPResponseException as exc:
        return {**report,"smtp_code":exc.smtp_code}
    except (OSError,smtplib.SMTPException,ValueError) as exc:
        return {**report,"error_type":type(exc).__name__}


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--approved-offline-local-milter",action="store_true")
    options=parser.parse_args(argv)
    if not options.approved_offline_local_milter:
        print(json.dumps({
            "status":"MILTER_ONLINE_TEST_NOT_REQUESTED",
            "network_calls":0,"customer_mail_delivered":False,
            "production_mx_changed":False,
        },sort_keys=True))
        return 0
    output=probe_milter_online()
    print(json.dumps(output,sort_keys=True))
    return 0 if output["status"]=="MILTER_ONLINE_SYNTHETIC_DATA_ACCEPTED" else 2


if __name__=="__main__":
    raise SystemExit(main())
