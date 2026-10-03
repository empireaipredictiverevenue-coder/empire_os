#!/usr/bin/env python3
"""One-time OAuth authorisation for the Empire Gmail relay."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from empire_os.gmail_api_transport import GMAIL_SCOPES


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
    args = parser.parse_args()

    client = Path(args.client)
    token = Path(args.token)

    if not client.is_file():
        raise SystemExit(
            f"OAuth client file missing: {client}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client),
        GMAIL_SCOPES,
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

    token.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    token.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )
    os.chmod(token, 0o600)

    print("EMPIRE_GMAIL_OAUTH=AUTHORIZED")
    print(f"TOKEN_FILE={token}")
    print("SCOPES=" + ",".join(credentials.scopes or []))
    print("NO_EMAIL_SENT=true")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
