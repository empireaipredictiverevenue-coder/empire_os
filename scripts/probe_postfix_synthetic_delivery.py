"""ONE synthetic DATA delivery to disposable, loopback-only Postfix stage.

Explicit opt-in, verified isolated staging fixture. No real company sender,
customer data, original-message claims, public mail routing or SMTP outbound.
The test reads only files in the explicit temporary owner-controlled Maildir.
"""
from __future__ import annotations

import argparse
from email.message import EmailMessage
from email.policy import SMTP as SMTP_POLICY
from hashlib import sha256
from pathlib import Path
import json
import os
import smtplib
import stat
import time
from uuid import UUID

from empire_os.owned_postfix_staging_profile import DOMAIN, HOST
from scripts.probe_postfix_staging_smtp_rcpt import BannerCapturingSMTP

INTENT = str(UUID(int=121))
RCPT = f"reply+{INTENT}@{DOMAIN}"
MESSAGE_ID = "<empire-synthetic-postfix-fixture@offline.invalid>"
MARKER = "EMPIRE_SYNTHETIC_STAGING_DATA_DELIVERY_V1"
MAX_SECONDS = 16


def _stage(root: Path) -> Path:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("isolated fixture root required")
    if not root.name.startswith("empire-postfix-stage-") or not root.is_dir():
        raise ValueError("unrecognized staging root")
    # A protected marker is placed by the isolated receiver owner, NEVER by
    # this reader/sender. The root directory is not arbitrary production mail.
    proof=root/".empire-ci-mail-delivery-test"
    if proof.is_symlink() or not proof.is_file() or proof.read_text()!="CI_CONTAINER_NETWORK_NONE\n":
        raise ValueError("owner provisioned isolated marker absent")
    if stat.S_IMODE(proof.stat().st_mode) != 0o600 or proof.stat().st_uid != 0:
        raise ValueError("isolated owner marker not protected")
    maildir = root/"maildir"/f"jev-{INTENT}"
    if root.is_symlink() or (root/"maildir").is_symlink() or maildir.is_symlink():
        raise ValueError("staging Maildir symlink denied")
    return maildir


def verify_one_synthetic_delivery(root: Path) -> dict[str, object]:
    mailbox=_stage(root)
    if mailbox.exists():
        raise ValueError("staging recipient mailbox must start empty")
    fixture=EmailMessage()
    fixture["Message-ID"]=MESSAGE_ID
    fixture["From"]="synthetic-fixture@offline.invalid"
    fixture["To"]=RCPT
    fixture["Subject"]="Synthetic Postfix delivery integration test ONLY"
    fixture.set_content(MARKER)
    serialized=fixture.as_bytes(policy=SMTP_POLICY)
    assert len(serialized) < 1024

    with BannerCapturingSMTP("127.0.0.1",2525,timeout=4) as client:
        welcome=getattr(client,"welcome",b"")
        if not isinstance(welcome,bytes) or HOST.encode() not in welcome:
            raise ValueError("isolated SMTP banner mismatch")
        if client.ehlo("offline.invalid")[0] != 250:
            raise ValueError("isolated EHLO not accepted")
        if any(x in client.esmtp_features for x in ("auth","starttls")):
            raise ValueError("unexpected live SMTP authentication feature")
        if client.mail("synthetic-fixture@offline.invalid")[0] != 250:
            raise ValueError("isolated test sender rejected")
        if client.rcpt(RCPT)[0] not in (250,251):
            raise ValueError("explicit synthetic recipient not admitted")
        status,_=client.data(serialized)
        if status != 250:
            raise ValueError("synthetic SMTP DATA not accepted")

    result=[]
    for _ in range(MAX_SECONDS*5):
        result = [
            p for folder in (mailbox/"new", mailbox/"cur")
            if folder.is_dir()
            for p in folder.iterdir()
            if p.is_file() and not p.is_symlink()
        ]
        if result:
            break
        time.sleep(.2)
    if len(result) != 1:
        raise ValueError("exactly one Maildir delivery required")
    body=result[0].read_bytes()
    if MESSAGE_ID.encode() not in body or MARKER.encode() not in body or RCPT.encode() not in body:
        raise ValueError("synthetic original RFC contents not preserved")
    if len(body) >= 4096 or not (mailbox/"tmp").is_dir():
        raise ValueError("unexpected Maildir structure or fixture size")
    if any((mailbox/"tmp").iterdir()):
        raise ValueError("unexpected partially delivered Maildir temp")
    return {
        "schema_version":"empire.mail.postfix_synthetic_delivery_proof.v1",
        "mode":"ISOLATED_OFFLINE_FIXTURE",
        "status":"ONE_SYNTHETIC_MESSAGE_DURABLY_DELIVERED",
        "smtp_data_accepted":True,
        "maildir_item_count":1,
        "original_message_id_verified":True,
        "synthetic_payload_sha256":sha256(serialized).hexdigest(),
        "delivered_maildir_bytes_sha256":sha256(body).hexdigest(),
        "deliver_to_real_contact":False,
        "sender_authentication_verified":False,
        "original_smtp_source_attested":False,
        "replay_idempotency_verified":False,
        "production_ready":False,
        "customer_mail_delivered":False,
        "production_mx_changed":False,
        "execution_authority":"fixture-only",
    }


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Isolated fixture-only Postfix DATA proof")
    parser.add_argument("--approved-isolated-synthetic-delivery", action="store_true")
    parser.add_argument("--staging-root", type=Path)
    opts=parser.parse_args(argv)
    if not opts.approved_isolated_synthetic_delivery or opts.staging_root is None:
        print(json.dumps({"status":"EXPLICIT_ISOLATED_DELIVERY_TEST_NOT_REQUESTED",
            "network_connections":0,"production_mx_changed":False,
            "customer_mail_delivered":False},sort_keys=True))
        return 0
    try:
        evidence=verify_one_synthetic_delivery(opts.staging_root)
    except (OSError,ValueError,smtplib.SMTPException) as exc:
        print(json.dumps({"status":"HOLD_SYNTHETIC_DELIVERY_UNVERIFIED",
            "error_type":type(exc).__name__,"production_mx_changed":False,
            "customer_mail_delivered":False},sort_keys=True))
        return 2
    print(json.dumps(evidence,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
