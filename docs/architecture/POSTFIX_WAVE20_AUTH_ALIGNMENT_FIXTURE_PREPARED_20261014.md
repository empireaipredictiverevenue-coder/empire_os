# EmpireOS — Wave 20 sender-authentication fixture preparation

Date: 2026-10-14
Isolated test worktree: /home/ubuntu/empire_worktrees/postfix_isolated_ci_20261014
Starting independently verified mail integration: 5b48569a.

## Prepared but not deployed

- scripts/ci_rspamd_local_dns_fixture.py: isolated 127.0.0.1:5353 DNS fixture answering only reserved receiver.test synthetic SPF, DKIM and DMARC records, using an ephemeral test-generated public key.
- scripts/ci_rspamd_alignment_probe.py: offline signed and unsigned synthetic sender messages with strict positive and negative authentication-result checks and zero buyer identity or production authority.
- Both files passed Python syntax compilation.

## Critical limitation

The execution environment blocked the step to wire dependencies and run these new fixtures in disposable CI. No alternative permission bypass was attempted. The required dkim and dnslib Python packages are not installed in the connected EmpireOS host environment. Real positive SPF, DKIM and DMARC alignment is **NOT** verified. No new GitHub workflow was executed for these files.

Previously independent real Postfix/Rspamd test still passed:
https://github.com/empireaipredictiverevenue-coder/empire_os/actions/runs/38584681347

Verified prior result: Milter unavailable -> SMTP 451; Milter running -> synthetic SMTP 250; real sender authentication still false.

## Next acceptance gate

The test-only DNS and DKIM fixture must first be validated against genuine Rspamd SPF/DKIM/DMARC modules, with the local resolver pinned and Authentication-Results explicitly enabled for isolated local senders. False aligned-pass claims must fail.

Further production gates: protected original MTA queue/digest custody, Ed25519 signer authority, durable anti-replay, EmpireDB canonical tenant/contact and suppression binding, live transport and rollback before DNS/MX release.

No production listener, DNS change, customer mail send, database change, signing key or payment action occurred.

Official docs:
- https://docs.rspamd.com/configuration/options/
- https://docs.rspamd.com/modules/milter_headers/
- https://docs.rspamd.com/modules/dmarc/
