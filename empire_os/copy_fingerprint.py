"""Canonical identity for exact final outbound email wording (not send proof)."""
from __future__ import annotations
import hashlib
import json


def fingerprint_final_email(*, subject: str, body: str) -> str:
    if not isinstance(subject, str) or not subject.strip() or not isinstance(body, str) or not body.strip():
        raise ValueError('final email subject and body required')
    payload = json.dumps({'subject': subject, 'body': body}, sort_keys=True, ensure_ascii=False)
    return 'copy-sha256:' + hashlib.sha256(payload.encode('utf-8')).hexdigest()
