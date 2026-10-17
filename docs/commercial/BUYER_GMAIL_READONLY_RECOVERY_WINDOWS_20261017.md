# Empire AI Gmail buyer-reader reauthorisation — one Windows SSH session

17 October 2026 | Existing OAuth client and importer | No email sending | Founder action required

## What actually went wrong

Google answered invalid_grant when EmpireOS attempted to refresh the expired read-only Gmail token. That requires the mailbox owner to complete new Google browser consent; the existing Google OAuth client ID/secret, scopes and internal poller are not being rebuilt.

On the first repair attempt the founder opened a Google browser callback at 127.0.0.1:38765 and got ERR_CONNECTION_RESET, despite Windows Test-NetConnection returning TcpTestSucceeded True. The remote Python OAuth listener had already exited and the original token had been safely restored. The SSH port-forwarding listener can keep accepting Windows TCP while its remote upstream server is absent: a successful local port test alone does not prove that the Google callback can be processed.

## Correct procedure: single PowerShell SSH session

1. Close any **previous** SSH -N tunnel window forwarding Windows port 38765. Leave normal unrelated SSH terminals alone. Do not keep two port forwarders on the same local port.
2. Open ONE new PowerShell window on Windows and run this single command:

    ssh -tt -o ExitOnForwardFailure=yes -L 127.0.0.1:38765:127.0.0.1:38765 ubuntu@62.210.95.205 "cd /srv/empire_os && bash scripts/renew_buyer_gmail_readonly_20261017.sh --apply"

3. This establishes Windows-to-EmpireOS port forwarding **in the same SSH session** as the remote OAuth callback listener. Keep this PowerShell window open for the entire Google consent process. Do not Ctrl+C after the URL appears.
4. Wait for the message GOOGLE_BROWSER_CONSENT_REQUIRED, then OPEN IN YOUR WINDOWS BROWSER. Open the **new** Google account authorization link shown in that session. DO NOT reuse or refresh an older 127.0.0.1 callback tab.
5. Select the original buyer-read account flavag83@gmail.com, NOT the official sender Workspace mailbox. The allowed Google permission is Gmail read-only, and no send or modify Gmail scope is requested.
6. After Google consents, it redirects to the temporary local 127.0.0.1:38765 callback. The browser should say EmpireOS Gmail read-only permission granted. The server script must then print EXACT_FOUNDER_BUYER_GMAIL_READONLY_ACCOUNT_VERIFIED and BUYER_GMAIL_READONLY_REAUTHORIZED. Only then is the reconnect finished.

If the PowerShell terminal disconnects or ERR_CONNECTION_RESET recurs, do not paste the private browser callback or authorization code into a chat. Inspect only safe local status: is the PowerShell SSH+authoriser process still running? A site reset with no remote listener is expected. Start a **new single-session attempt** using the command above. The existing renewal script restores the former private token automatically when a normal attempt fails.

If another Windows program already owns local port 38765, the SSH command will fail immediately rather than silently using a dead tunnel. Free that local port by closing the old tunnel first; do NOT disable Windows firewall or proxy globally.

## Independent verification, no SMTP or consumer traffic

Once the terminal reports success, use the existing read-only poller on EmpireOS:

    cd /srv/empire_os
    ./.venv/bin/python -m scripts.poll_buyer_gmail_readonly

The poll prints bounded counts and sanitized original-message IDs without sending messages. Do not assume buyer identities or CRM consent from observed Gmail threads; the Founder Mailbox EmpireDB-only model remains separate until reconciled. Next run the existing canonical buyer relationship reconciler only after confirming the source and suppression ledger; no unsolicited messages.

The operator script is already committed as e501df4c:
- scripts/renew_buyer_gmail_readonly_20261017.sh
- tests/test_renew_buyer_gmail_readonly_20261017.py
- Existing authoriser: scripts/authorize_buyer_gmail_readonly.py
- Exact read scope: https://www.googleapis.com/auth/gmail.readonly

The owner can check preflight safely with:

    cd /srv/empire_os
    bash scripts/renew_buyer_gmail_readonly_20261017.sh --preflight

Preflight does NOT refresh the token or perform an OAuth browser authorization. The actual --apply explicitly requires founder Google sign-in and consent, and the script verifies the selected mailbox identity before replacing the original token.

Do not copy private tokens, OAuth callback URLs, state strings, authorization codes or the server's credential-file bytes to ChatGPT, documents or Slack.
