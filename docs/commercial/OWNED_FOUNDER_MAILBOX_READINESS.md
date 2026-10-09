# Empire AI Founder Mailbox — Owned, read-only IMAP integration

**Engineering state:** IMAP adapter implemented, provider selection corrected, tested with injected IMAP sessions. **Production mail connectivity not proven.** This is not approval for outbound, suppression modifications or commercial reply admission.

## Root cause and correction

The Founder Mailbox read API previously chose `ResendMailboxProvider` when no explicit provider was injected. The 9 October 2026 in-process observer returned `503: mailbox_provider_unavailable:RuntimeError`, even though the founder requires Empire AI's **own professional mailbox**, not Resend or AWS.

`create_founder_mailbox_router()` now defaults to the sovereign, stdlib-backed `OwnedIMAPMailboxProvider`. An explicitly supplied test/provider object still works, but a runtime request to select Resend via `EMPIRE_FOUNDER_MAILBOX_PROVIDER=resend` fails closed. No credential or IMAP endpoint is inferred. Existing user mail must be properly provisioned first.

## Connection contract (set on the existing Founder API runtime, not in Git)

| Environment setting | Meaning |
| --- | --- |
| `EMPIRE_FOUNDER_MAILBOX_PROVIDER=owned_imap` | Optional explicit mode; default is `owned_imap` |
| `EMPIRE_FOUNDER_IMAP_HOST` | Actual IMAP TLS host of the **owned** mail service, supplied by the mailbox operator; **do not assume the domain itself is the IMAP host** |
| `EMPIRE_FOUNDER_IMAP_PORT=993` | IMAPS port (default 993), with normal server certificate verification |
| `EMPIRE_FOUNDER_IMAP_USER` | Mailbox login account for the founder-owned mailbox |
| `EMPIRE_FOUNDER_IMAP_PASSWORD` | Mailbox-specific credential; **never paste into chats, logs, Git, runtime snapshots or diagnostic tickets** |
| `EMPIRE_FOUNDER_IMAP_INBOX=INBOX` | Existing inbound folder (default `INBOX`) |
| `EMPIRE_FOUNDER_IMAP_SENT=Sent` | Existing Sent folder name; verify actual server naming |

Supply these through the **existing founder service's securely permissioned environment**, using a root-owned `0600` EnvironmentFile or a systemd credentials mechanism as appropriate. The existing deployment service must actually receive those values; setting them in an unrelated terminal is not production configuration. The IMAP credential only permits read access if the account's server-side ACLs support it; use a read-only account if available. Do not alter mailbox DNS, MX records, outbound SMTP, sender reputation, automation timers or startup units as part of this code change.

## Production recovery and safe activation order

**Verified outage (9 October 2026):** adding a systemd drop-in with the mandatory line
`EnvironmentFile=/etc/empire/founder-imap.env` before creating the file caused
`empire-founder-dashboard-api.service` to fail with systemd `Result=resources`,
`Failed to load environment files: No such file or directory` and a restart loop.

The correct service is `empire-founder-dashboard-api.service` (loopback
`127.0.0.1:8766`, existing environment `/etc/empire_os.env`), **not**
`founder-dashboard-api.service`. The service-aware verifier tolerates brief loopback startup races without restarting again. The interactive `ubuntu` shell does not inherit
that protected service environment. Testing the interactive environment alone
therefore does not prove service configuration.

**If this exact startup failure occurs, restore just the Founder API first:**

```bash
cd /srv/empire_os
sudo sed -i \
  's|^EnvironmentFile=/etc/empire/founder-imap.env$|EnvironmentFile=-/etc/empire/founder-imap.env|' \
  /etc/systemd/system/empire-founder-dashboard-api.service.d/20-owned-imap.conf
sudo systemctl daemon-reload
sudo systemctl reset-failed empire-founder-dashboard-api.service
sudo systemctl restart empire-founder-dashboard-api.service
systemctl is-active empire-founder-dashboard-api.service
./.venv/bin/python scripts/verify_owned_imap_mailbox.py --service
```

The leading `-` makes an **optional** EnvironmentFile: systemd does not take
Founder API offline just because the new IMAP secret file is absent. It grants
no inbox, outbound, suppression or commercial authority. A healthy service can
correctly report `CONFIGURATION_REQUIRED` for its optional mailbox integration.

**Before configuring real mail access**, create the protected secret file
interactively (never print or source it and never put the values in Git/chat):

```bash
sudo install -d -m 0700 -o root -g root /etc/empire
sudo touch /etc/empire/founder-imap.env
sudo chmod 0600 /etc/empire/founder-imap.env
sudoedit /etc/empire/founder-imap.env
```

Fill in the actual owned provider's IMAP TLS host, login and mailbox-specific
password, and confirm the server's Sent-folder name. The systemd drop-in should
reference the existing file as
`EnvironmentFile=-/etc/empire/founder-imap.env`. After the protected file is
complete, restart **only** `empire-founder-dashboard-api.service` and verify
with `./.venv/bin/python scripts/verify_owned_imap_mailbox.py --service-probe`.
The service-aware probe uses the *actual running API*, not the interactive
shell's environment, and does not disclose messages or credentials.

If the `--service` result is `ROUTE_NOT_DEPLOYED`, the running process has not
loaded the new read-only mailbox code; a controlled restart of this single
service is appropriate after confirming the environment file is optional or
already present. Never restart unrelated EmpireOS workers/Cloudflare/Caddy to
recover this API.

## One clean verification path

1. Without connecting to the provider, run:

   ```bash
   cd /srv/empire_os
   ./.venv/bin/python scripts/verify_owned_imap_mailbox.py
   ```

   `CONFIGURATION_REQUIRED` (exit 2) means no validated configuration in that process. `CONFIGURED_UNPROVEN` (exit 2) means the settings are present but not tested.

2. From the same securely provisioned runtime identity (once configured), explicitly run:

   ```bash
   ./.venv/bin/python scripts/verify_owned_imap_mailbox.py --probe
   ```

   `READ_PROBE_SUCCESS` (exit 0) means TLS IMAP authenticated and could read both folders in `EXAMINE`/read-only mode. At most one message per folder is fetched; no message IDs, sender emails, body text or credentials appear in the diagnostic output. A failed probe reports only a fixed sanitized reason.

3. Verify `GET /v1/founder-mailbox/readiness` reports `READY_FOR_READ_PROBE` before checking `summary` or `threads`. The API must be deployed into its existing authenticated founder dashboard before operator use; **no service restart or production activation was performed by this integration**.

4. Examine the existing `runtime/conversations_replies_control/collector_health_latest.json`, `identity_bridge_latest.json` and `latest.json` **after** the owned provider is proved operational. Never count provider-only inbound mail as canonical buyer conversations. Do not promote hashed passive observations to identity authority without the original outbound intent/tenant/sender match.

## Safety and truth boundaries

- `IMAP4_SSL` with certificate validation, `SELECT readonly=True`, `UID SEARCH`, bounded `UID FETCH BODY.PEEK[]<0.32768>`, 50-message maximum and no `STORE`/`EXPUNGE`/`APPEND` or mark-as-read operation.
- Message identity uses actual RFC Message-ID where available plus mailbox-scoped `UIDVALIDITY:UID`, both subject to separate canonical binding checks. An IMAP UID, sender address, subject or inferred alias does **not** establish authenticated contact identity.
- The Founder API **never exposes raw owned-IMAP Message-ID as canonical evidence** in the legacy passive observer's read model. It identifies these events as provider-only and `canonical_buyer_conversation_verified=false`.
- IMAP does not provide the canonical outbound suppression ledger. `suppression_evidence_complete=false` blocks draft previews for the owned provider until a separate verified suppression bridge exists; an empty IMAP suppression list is never represented as confirmed unsuppressed.
- Provider message text is treated as untrusted content; it is not persisted by the IMAP provider. Body retrieval is memory-bounded and never triggers LLM/tool execution, outbound sends or DB writes.
- The Founder API no longer uses Resend implicitly. Existing `ResendMailboxProvider` can remain in source for test/migration compatibility but is not selected by the zero-argument runtime router.

## Remaining external/commercial gates

**Operational mailbox provisioning and the dedicated runtime environment** are still required. Reading a real inbox alone will not resolve a canonical buyer conversation; deterministic provider-message → original sent intent → tenant/contact identity joins and source authentication must pass the existing quarantine gates. A real buyer response cannot be claimed without those results. The founder should not be asked to reapprove generic SkillForge engineering or repeat the same observer diagnostics while awaiting genuine mailbox readiness.
