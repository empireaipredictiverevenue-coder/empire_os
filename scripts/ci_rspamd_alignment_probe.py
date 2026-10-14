"""Real isolated Rspamd SPF/DKIM/DMARC fixture, never production identity.

Requires owner-managed container with --network none and local fixture DNS.
Produces bounded boolean proof only, no original RFC, private key or contact.
This validates synthetic *message* authentication checks, not original MTA
queue custody, signed ingress receipts or real buyer domain ownership.
"""
from __future__ import annotations

import argparse
from email.message import EmailMessage
from email.policy import SMTP as SMTP_POLICY
from email.parser import BytesParser
from pathlib import Path
import smtplib
import time
import dkim

from scripts.probe_postfix_staging_smtp_rcpt import ALLOWED_RCPT, HOST, BannerCapturingSMTP

GOOD = "verified.receiver.test"
BAD = "forged.receiver.test"


def _message(sender: str, marker: str) -> bytes:
    msg=EmailMessage()
    msg["Message-ID"] = f"<{marker}@receiver.test>"
    msg["From"] = sender
    msg["To"] = ALLOWED_RCPT
    msg["Subject"] = "Offline source-authentication fixture"
    msg.set_content(f"EMPIRE_OFFLINE_{marker}_TEST_ONLY")
    return msg.as_bytes(policy=SMTP_POLICY)


def _send(raw: bytes, sender: str) -> int:
    with BannerCapturingSMTP("127.0.0.1",2525,timeout=17) as client:
        if HOST.encode() not in getattr(client,"welcome",b""):
            raise ValueError("unexpected non-staging SMTP banner")
        if client.ehlo("offline.invalid")[0] != 250:
            raise ValueError("offline receiver failed EHLO")
        if client.mail(sender)[0] != 250:
            raise ValueError("fixture SMTP MAIL not accepted")
        if client.rcpt(ALLOWED_RCPT)[0] not in (250,251):
            raise ValueError("fixture exact recipient not accepted")
        try:
            return client.data(raw)[0]
        except smtplib.SMTPResponseException as error:
            return error.smtp_code


def _maildir_new(stage: Path) -> set[str]:
    mailbox=stage/"maildir"/"jev-00000000-0000-0000-0000-000000000079"
    return {
        str(file) for category in ("new","cur")
        for file in (mailbox/category).iterdir()
        if file.is_file() and not file.is_symlink()
    }


def _wait_new(stage: Path, before: set[str]) -> bytes:
    for _ in range(70):
        added = _maildir_new(stage)-before
        if len(added)==1:
            file=Path(next(iter(added)))
            if file.stat().st_size > 48000:
                raise ValueError("unbounded synthetic Milter message")
            return file.read_bytes()
        if len(added)>1:
            raise ValueError("multiple messages delivered for one fixture")
        time.sleep(.2)
    raise ValueError("no actual Maildir delivery for fixture")


def _auth_headers(raw: bytes) -> str:
    parsed=BytesParser().parsebytes(raw,headersonly=True)
    values=parsed.get_all("Authentication-Results", [])
    if len(values) != 1:
        raise ValueError("exactly one verifier-added Authentication-Results required")
    return str(values[0]).lower()


def run_fixture(stage: Path, private_key: Path) -> dict:
    if stage.parent != Path("/tmp") or not stage.name.startswith("empire-postfix-stage-"):
        raise ValueError("exact isolated stage directory required")
    if private_key.is_symlink() or not private_key.is_file() or private_key.parent != stage:
        raise ValueError("ephemeral container-private signer required")
    good=_message(f"agent@{GOOD}","good-signed")
    sign=dkim.sign(
        good, selector=b"s1", domain=GOOD.encode("ascii"),
        privkey=private_key.read_bytes(),
        include_headers=[b"from",b"to",b"subject",b"message-id"],
        canonicalize=(b"relaxed",b"relaxed"),
    )
    signed=sign+good
    seen=_maildir_new(stage)
    status=_send(signed,f"agent@{GOOD}")
    if status != 250:
        raise ValueError(f"positive verifier fixture not accepted: {status}")
    good_body=_wait_new(stage,seen)
    auth=_auth_headers(good_body)
    print("POSITIVE_AUTH_RESULT_FIXTURE="+auth[:700],flush=True)
    print("POSITIVE_AUTH_HEADER_METHODS="+",".join(
        f"{name}:{'pass' if name+'=pass' in auth else 'not-pass'}"
        for name in ("spf","dkim","dmarc")
    ),flush=True)
    if not all(name+"=pass" in auth for name in ("spf","dkim","dmarc")):
        raise ValueError("local positive SPF/DKIM/DMARC alignment not all proven")

    # Attacker fixture has no DKIM and deliberately publishes SPF -all and
    # a nonaligned RFC5322 From. A 250 alone is NOT authentication evidence.
    seen=_maildir_new(stage)
    bad=_message(f"forgery@{BAD}","bad-unsigned")
    status=_send(bad,f"forgery@{BAD}")
    if status==250:
        bad_body=_wait_new(stage,seen)
        bad_auth=_auth_headers(bad_body)
        if "spf=pass" in bad_auth or "dkim=pass" in bad_auth or "dmarc=pass" in bad_auth:
            raise ValueError("forged unaligned sender incorrectly authenticated")
        negative_outcome="UNAUTHENTICATED_ACCEPTED_WITHOUT_QUARANTINE"
    elif 400 <= status < 600:
        negative_outcome="UNAUTHENTICATED_REFUSED_BY_MTA"
    else:
        raise ValueError("unsupported forged-sender result")
    return {
        "schema_version":"empire.mail.offline_rspamd_alignment.v1",
        "mode":"NETWORK_DISABLED_FIXTURE",
        "status":"REAL_OFFLINE_SPF_DKIM_DMARC_ALIGNMENT_PASS_AND_NEGATIVE_VERIFIED",
        "positive_smtp_status":250,
        "positive_spf":True,
        "positive_dkim":True,
        "positive_dmarc":True,
        "negative_no_authenticated_pass":True,
        "negative_quarantine_verified":False,
        "production_authentication_enforcement_verified":False,
        "negative_mta_result":negative_outcome,
        "real_sender_proven":False,
        "independent_ingress_receipt_signed":False,
        "canonical_buyer_verified":False,
        "production_mx_changed":False,
    }


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--approved-isolated-auth-fixture",action="store_true")
    parser.add_argument("--stage",type=Path)
    parser.add_argument("--private-key",type=Path)
    args=parser.parse_args(argv)
    if not args.approved_isolated_auth_fixture:
        print("OFFLINE_ALIGNMENT_TEST_NOT_REQUESTED")
        return 0
    if args.stage is None or args.private_key is None:
        raise SystemExit("HOLD_MISSING_ISOLATED_FIXTURE")
    result=run_fixture(args.stage,args.private_key)
    import json
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
