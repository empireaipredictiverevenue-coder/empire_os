#!/usr/bin/env python3
"""One-time OAuth authorisation for the Empire Gmail relay."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import os,stat
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from empire_os.gmail_api_transport import GMAIL_SCOPES, build_gmail_service, _write_token
from empire_os.google_workspace_mailbox import SCOPES as WORKSPACE_MAILBOX_SCOPES, EXPECTED_ACCOUNT


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client",
        default=(
            "/srv/empire_os/runtime/secrets/"
            "google-workspace-internal-oauth-client.json"
        ),
    )
    parser.add_argument(
        "--token",
        default=(
            "/srv/empire_os/runtime/secrets/"
            "google-workspace-internal-token.json"
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
    )
    parser.add_argument(
        "--mailbox-read",
        action="store_true",
        help="Explicitly reauthorise the same Workspace sender for Gmail read-only inbox access",
    )
    parser.add_argument(
        "--permit-draft-compose",
        action="store_true",
        help="Explicit Workspace owner OAuth reconsent for full draft-only MIME edits",
    )
    args = parser.parse_args(argv)
    if args.mailbox_read and args.permit_draft_compose:
        parser.error("choose one explicit Workspace permission mode")

    client = Path(args.client)
    token = Path(args.token)

    if not client.is_file():
        raise SystemExit(
            f"OAuth client file missing: {client}"
        )

    compose_scope="https://www.googleapis.com/auth/gmail.compose"
    requested_scopes = (
        [*WORKSPACE_MAILBOX_SCOPES,compose_scope]
        if args.permit_draft_compose
        else WORKSPACE_MAILBOX_SCOPES if args.mailbox_read else GMAIL_SCOPES
    )
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client),
        requested_scopes,
    )

    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=args.port,
        open_browser=False,
        authorization_prompt_message=(
            "\nOPEN THIS URL IN YOUR WINDOWS BROWSER:\n{url}\n"
        ),
        success_message=(
            "Empire Gmail OAuth authorised. "
            "You can close this browser tab."
        ),
        access_type="offline",
        prompt="consent",
    )

    if args.mailbox_read or args.permit_draft_compose:
        # Never replace the established sender with a grant from another
        # account or missing prior read/send permissions.
        if not set(requested_scopes).issubset(set(credentials.scopes or [])):
            raise SystemExit("WORKSPACE_MAILBOX_SCOPES_NOT_GRANTED; no token replaced")
        try:
            profile = build_gmail_service(credentials).users().getProfile(userId="me").execute()
        except Exception:
            raise SystemExit("WORKSPACE_MAILBOX_ACCOUNT_NOT_VERIFIED; no token replaced") from None
        if str(profile.get("emailAddress") or "").lower() != EXPECTED_ACCOUNT:
            raise SystemExit("WORKSPACE_MAILBOX_ACCOUNT_MISMATCH; no token replaced")

    token.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    if args.permit_draft_compose:
        # This is sensitive credential custody. Copy the previous ORIGINAL
        # token only to a new 0600 private file, after successful consent
        # and exact Gmail identity checks, never print its bytes.
        if (not token.is_file() or token.is_symlink()
            or stat.S_IMODE(token.stat().st_mode)!=0o600):
            raise SystemExit("ORIGINAL_WORKSPACE_TOKEN_CUSTODY_UNVERIFIED")
        stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup=token.with_name(token.name+".pre-compose-"+stamp)
        if backup.exists() or backup.is_symlink():
            raise SystemExit("ORIGINAL_WORKSPACE_TOKEN_BACKUP_CONFLICT")
        fd=os.open(backup,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(token.read_bytes());f.flush();os.fsync(f.fileno())
        except Exception:
            backup.unlink(missing_ok=True)
            raise
    _write_token(token, credentials.to_json())

    print("EMPIRE_GMAIL_OAUTH=AUTHORIZED")
    print(f"TOKEN_FILE={token}")
    print("SCOPES=" + ",".join(credentials.scopes or []))
    print("NO_EMAIL_SENT=true")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
