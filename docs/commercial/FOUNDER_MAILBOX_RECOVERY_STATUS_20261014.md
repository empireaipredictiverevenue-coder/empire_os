# Founder mailbox recovery — 14 October 2026

## Confirmed on running EmpireOS

- Existing Gmail HTTPS relay configured with founder sender and reply-to, and remains in OBSERVE with sending disabled.
- Correction verified 14 October: the live relay uses `google-workspace-internal-token.json` from the durable project `empireos-workspace-mail-511518`, created and authorised on 13 October. Its refresh token exists, matches the internal OAuth client and refreshes successfully. The separate `google-workspace-token.json` from `superb-garden-511210-a1` is legacy and **is not the live relay token**. Do not reauthorise or replace the working setup simply because access tokens expire.
- Google verified the live project's `gmail.send` scope. No email was sent. Google's OAuth consent-screen publishing state was not independently read from Cloud Console.
- Actual Workspace mailbox identity is not verified by the send-only scope; Gmail profile lookup returned insufficient permission.
- Founder inbox reader is not configured in the running API; separate IMAP credentials are absent.
- Root domain MX routes to Google; the founder mail subdomain MX points to an older inbound service, inconsistent with the active Resend-labelled webhook.
- SPF and DKIM for the founder mail subdomain have not passed verification.

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
4. Verify SPF, DKIM, DMARC and a controlled founder-approved send-and-reply test; keep prospect outreach governed.

**Status: send OAuth repaired; first-party read path implemented but not activated; sender owner, inbox and end-to-end replies remain unverified. No real outbound message, service restart or DNS change.**
