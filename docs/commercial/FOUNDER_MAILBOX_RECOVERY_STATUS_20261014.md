# Founder mailbox recovery — 14 October 2026

## Confirmed on running EmpireOS

- Existing Gmail HTTPS relay configured with founder sender and reply-to, and remains in OBSERVE with sending disabled.
- Correction verified 14 October: the live relay uses `google-workspace-internal-token.json` from the durable project `empireos-workspace-mail-511518`, created and authorised on 13 October. Its refresh token exists, matches the internal OAuth client and refreshes successfully. The separate `google-workspace-token.json` from `superb-garden-511210-a1` is legacy and **is not the live relay token**. Do not reauthorise or replace the working setup simply because access tokens expire.
- Google verified the live project's `gmail.send` scope. No email was sent. Google's OAuth consent-screen publishing state was not independently read from Cloud Console.
- Actual Workspace mailbox identity is not verified by the send-only scope; Gmail profile lookup returned insufficient permission.
- Founder inbox reader is not configured in the running API; separate IMAP credentials are absent.
- Root MX routes to Google; the mail subdomain MX advertises Amazon SES infrastructure while signed incoming mail is handled by the active Resend webhook. Founder-controlled test messages DID reach that webhook on 13 October; this DNS/provider combination is not proven broken. Sovereign inbound migration remains separate.
- Actual received-test headers show SPF, DKIM and DMARC passed on 13 October; this supersedes the earlier DNS-only warning.

## Engineering repaired and tested

- Explicit Google Workspace Gmail read-only adapter reuses the existing Founder API, not a new mail or agent runtime.
- An optional OAuth consent route requests inbox-read permission, verifies the **exact founder account**, and never replaces the current token on mismatch.
- Sending-token refresh preserves any additional authorised inbox-read scope.
- Read-only service proof and a combined one-hit mailbox readiness checker are available.
- Default service configuration remains unchanged until account identity and consent are proven.

## Remaining activation gates

1. Account-holder grants read-only permission to the real founder Workspace account. This requires an external Google sign-in; the running send-only token cannot grant it automatically.
2. Deploy only the explicit Workspace reader setting through the existing privileged Founder API service, then verify one bounded inbox and sent-folder read. Remote Commander currently rejects privileged service changes.
3. Validate Workspace acceptance of the mail subdomain and both sender/reply addresses before changing MX or retiring the old inbound provider. Preserve existing incoming mail during migration.
4. Preserve the successful 13 October send/reply test evidence; do not repeat it merely to check the already-proven path. A separate proof is only needed after a future change to the inbound provider or direct Workspace inbox. Keep prospect outreach governed.

**Status 14 October: actual 13 October founder-controlled tests verified professional sending and forwarded base/threaded replies. Direct Workspace inbox access and fully sovereign inbound migration remain incomplete. No new message sent, service restart or DNS change by this recovery.**
