#!/usr/bin/env python3
"""Founder-only, interactive first CRM password creation over server loopback.

Reads the approved invitation token locally; never prints, emails or logs it.
The founder enters a strong password via an SSH TTY (not shell arguments).
"""
from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
import pwd
import stat
import sys
from datetime import datetime,timezone
from http.client import HTTPConnection

BASE="http://127.0.0.1:8783"
RECORD=Path("/var/lib/empire-crm-first-party/founder_invitation/pending_invitation.json")
TENANT="708efd4b-53b2-43d7-961d-1cecab67f17a"
SUBJECT="founder:phil_livesley"
EMAIL="flavag83@gmail.com"


def invitation() -> dict:
    expected_uid=pwd.getpwnam("ubuntu").pw_uid
    if (RECORD.is_symlink() or not RECORD.is_file()
        or RECORD.stat().st_uid!=expected_uid
        or stat.S_IMODE(RECORD.stat().st_mode)!=0o600
        or stat.S_IMODE(RECORD.parent.stat().st_mode)!=0o700):
        raise RuntimeError("founder invitation vault unavailable")
    raw=json.loads(RECORD.read_text(encoding="utf-8"))
    if (raw.get("status")!="PENDING_NOT_SENT"
        or raw.get("subject")!=SUBJECT
        or raw.get("tenant_id")!=TENANT
        or raw.get("login_email")!=EMAIL
        or not isinstance(raw.get("token"),str)
        or len(raw["token"])!=47 or not raw["token"].startswith("EI1_")
        or datetime.fromisoformat(raw["expires_at_utc"]) <= datetime.now(timezone.utc)):
        raise RuntimeError("founder invitation expired or unverified")
    return raw


def post(path: str, payload: dict, token: str | None=None) -> tuple[int,dict]:
    if path not in ("/v1/revenue-crm/auth/accept-invite","/v1/revenue-crm/auth/login"):
        raise ValueError("unsupported local CRM endpoint")
    headers={"Content-Type":"application/json"}
    if token is not None:
        headers["Authorization"]="Bearer "+token
    connection=HTTPConnection("127.0.0.1",8783,timeout=8)
    try:
        connection.request("POST",path,
            body=json.dumps(payload,separators=(",",":")).encode("utf-8"),
            headers=headers)
        response=connection.getresponse()
        raw=response.read(8192)
        return response.status, json.loads(raw) if response.status==200 else {}
    finally:
        connection.close()


def get_authenticated(path: str,bearer: str) -> int:
    if path not in ("/v1/revenue-crm/prospects","/v1/revenue-crm/buyers"):
        raise ValueError("unsupported local CRM read")
    connection=HTTPConnection("127.0.0.1",8783,timeout=8)
    try:
        connection.request("GET",path+"?limit=1",headers={"Authorization":"Bearer "+bearer})
        response=connection.getresponse()
        response.read(200)
        return response.status
    finally:
        connection.close()


def main() -> int:
    if sys.argv[1:] != ["--interactive-first-login"]:
        print("CRM_FOUNDER_SETUP=BLOCKED_EXACT_FLAG_REQUIRED")
        return 3
    if os.geteuid()!=pwd.getpwnam("ubuntu").pw_uid or not sys.stdin.isatty():
        print("CRM_FOUNDER_SETUP=BLOCKED_SSH_TTY_AND_OWNER_REQUIRED")
        return 3
    try:
        record=invitation()
        print("Setting up your EmpireOS CRM founder login.")
        print("The password is entered privately and never shown or saved in chat.")
        first=getpass.getpass("Create CRM password (minimum 14 characters): ")
        if len(first)<14 or len(first)>256:
            print("CRM_FOUNDER_SETUP=INVALID_PASSWORD_LENGTH")
            return 2
        second=getpass.getpass("Confirm CRM password: ")
        if first!=second:
            print("CRM_FOUNDER_SETUP=PASSWORD_CONFIRMATION_MISMATCH")
            return 2
        status,reply=post("/v1/revenue-crm/auth/accept-invite",{
            "invitation_token":record["token"],
            "new_password":first,
            "tenant_id":TENANT,
        })
        if status!=200 or reply.get("accepted") is not True:
            print("CRM_FOUNDER_SETUP=INVITE_REDEMPTION_NOT_VERIFIED")
            return 4
        print("CRM_FOUNDER_INVITATION=REDEEMED")
        status,reply=post("/v1/revenue-crm/auth/login",{
            "email":EMAIL,"password":first,"tenant_id":TENANT,
        })
        first=""
        second=""
        if status!=200 or not isinstance(reply.get("access_token"),str):
            print("CRM_FOUNDER_SETUP=PASSWORD_LOGIN_NOT_VERIFIED")
            return 4
        bearer=reply["access_token"]
        a=get_authenticated("/v1/revenue-crm/prospects",bearer)
        b=get_authenticated("/v1/revenue-crm/buyers",bearer)
        if a!=200 or b!=200:
            print("CRM_FOUNDER_SETUP=AUTHENTICATED_TENANT_READ_FAILED")
            return 4
        print("CRM_FOUNDER_AUTHENTICATED_PROSPECTS=200")
        print("CRM_FOUNDER_AUTHENTICATED_BUYERS=200")
        print("CRM_FOUNDER_SETUP=FIRST_PARTY_LOGIN_VERIFIED")
        return 0
    except (OSError,RuntimeError,ValueError):
        print("CRM_FOUNDER_SETUP=BLOCKED_OR_UNVERIFIED_NO_AUTOMATIC_RETRY")
        return 4


if __name__=="__main__":
    raise SystemExit(main())
