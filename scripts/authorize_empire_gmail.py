#!/usr/bin/env python3
"""One-time OAuth authorisation for the Empire Gmail relay."""
from __future__ import annotations

import argparse
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from empire_os.gmail_api_transport import GMAIL_SCOPES, build_gmail_service, _write_token
from empire_os.google_workspace_mailbox import SCOPES as WORKSPACE_MAILBOX_SCOPES, EXPECTED_ACCOUNT


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client",
        default=(
            "/srv/empire_os/runtime/secrets/"
            "google-workspace-oauth-client.json"
        ),
    )
    parser.add_argument(
        "--token",
        default=(
            "/srv/empire_os/runtime/secrets/"
            "google-workspace-token.json"
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
    args = parser.parse_args()

    client = Path(args.client)
    token = Path(args.token)

    if not client.is_file():
        raise SystemExit(
            f"OAuth client file missing: {client}"
        )

    requested_scopes = WORKSPACE_MAILBOX_SCOPES if args.mailbox_read else GMAIL_SCOPES
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

    if args.mailbox_read:
        # Never replace the established sending token with a consent grant
        # from the wrong Google account or insufficient Gmail permissions.
        if not set(WORKSPACE_MAILBOX_SCOPES).issubset(set(credentials.scopes or [])):
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

    _write_token(token, credentials.to_json())

    print("EMPIRE_GMAIL_OAUTH=AUTHORIZED")
    print(f"TOKEN_FILE={token}")
    print("SCOPES=" + ",".join(credentials.scopes or []))
    print("NO_EMAIL_SENT=true")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
