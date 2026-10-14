# EmpireOS JEV GTM — Wave 13 Postfix Offline Receiver Staging

Date: 2026-10-14
Isolated branch: `feature/jev-gtm-v2-20261014`
Starting commit: `0e3084a2`
Mode: **OFFLINE STAGING ONLY**. No SMTP listener, production Postfix install, DNS/MX change, systemd change, mail send, funds or DB migration.

## Live source inventory and isolation

- Ubuntu `26.04.1 LTS`, canonical package index candidate `postfix 3.10.6-4ubuntu2.2`.
- Neither `/usr/sbin/postfix` nor `/usr/sbin/postconf`/OpenDKIM/OpenDMARC/Dovecot existed; no visible port 25, 465 or 587 listeners.
- Main `/srv/empire_os` is moving under other agents; none of its dirty state, service activation or credentials were modified.
- `mail.empire-ai.co.uk` A resolves to `216.128.149.56`, while the EmpireOS host is `62.210.95.205`; its current MX is SES `inbound-smtp.us-east-1.amazonaws.com`. No receiving process on EmpireOS was proven.
- Existing Founder mailbox still reported `owned_imap`, `configured=false`; another agent is independently preparing the canonical reply viewer. This branch did not deploy or alter its release.
- The existing Wave 12 producer requires the exact `reply+<lowercase UUID>@mail.empire-ai.co.uk` SMTP-envelope recipient. Ordinary `reply@mail.empire-ai.co.uk` has **no guaranteed JEV contact/intent binding** and must be a separate explicitly authorized mail route. No catch-all is allowed.

## Implementation

`empire_os/owned_postfix_staging_profile.py` constructs a strict static candidate profile:
- Isolated `/tmp/empire-postfix-stage-*` working root only; one explicit canonical test intent UUID and unprivileged fixture UID/GID, validated and embedded in the record.
- `main.cf` binds to `loopback-only`, IPv4, with empty `relay_domains`, `relayhost`, `virtual_alias_domains`, `smtpd_sasl_auth_enable=no`, and `smtpd_relay_restrictions=reject_unauth_destination`.
- `smtpd_recipient_restrictions` includes `reject_unlisted_recipient` and `reject_unauth_destination`. One known virtual mailbox domain, with EXACTLY one mapped `reply+UUID` recipient. No bare `reply@` mailbox, wildcard `@domain` or SMTP sender/submission service.
- `master.cf` describes only `127.0.0.1:2525` as the SMTP inet service. Mail pickup and local virtual delivery plumbing is present for a future contained acceptance check; no external outbound `smtp unix` transport is configured.
- Header/mime message-size budget is limited to 512 KiB as in Wave 12 signer. Production TLS, DKIM/SPF/DMARC verification and an authenticated raw-message MTA adapter **are not** configured and remain release blockers.
- Both the generator and a separate strict policy validator reject unknown parameter insertions, changed relay/recipient restrictions, new listeners, changed domains/UIDs, catch-all mappings and extra recipients. Validation produces only a SHA-256 and no alias/recipient private information.
- No private real intent IDs or credentials used: all tests reference synthetic UUIDs only.

`scripts/probe_owned_postfix_staging.py`:
- Default command does nothing.
- Explicit `--fixture-smoke`: constructs the three source files in a temporary 0700 directory, creates the files exclusively as 0600 with no-follow protection, checks byte-for-byte readback and deletes the temporary directory. No network, Postfix binary, postmap, SMTP port, Postfix service, DNS or mailbox call is made.
- Emits only a privacy-safe metadata receipt; `runtime_postfix_parser_verified=false`, `postmap_compiled=false`, `receiver_deployed=false`, `actual_mail_received=false`.

### Independent Ubuntu Postfix parser smoke

The Canonical `postfix 3.10.6-4ubuntu2.2` and `libnsl2` apt packages were downloaded with **apt-get download** into an auto-deleted temporary directory and extracted with `dpkg-deb -x` without package installation or service changes. The extracted bin/libs were invoked with `LD_LIBRARY_PATH` pointed only into the temporary package contents.

Real binary results:
- `postconf -c <isolated stage> -n`: **exit 0, 25 parsed main configuration settings**
- `postconf -c <isolated stage> -M`: **exit 0, 16 parsed master services**
- `postmap -c <isolated stage> hash:<staged recipients>`: **exit 1** due to missing `mail_owner=postfix` system account on the host. No role/user was created and no change was made to bypass the missing trusted owner.
- No SMTP session was attempted, no delivery or recipient rejection behavior was runtime-tested, and no `recipients.db` claim can be made.

**Interpreting this result**: A real Ubuntu Postfix parser has accepted both staged files. The future mail-service identity and postmap database compilation, plus local SMTP acceptance tests, remain unverified. The static configuration and recipient-map checks alone are not a mail-system security audit.

## Evidence, tests and gates

- `tests/test_owned_postfix_staging_profile.py` denies changed interfaces, new listeners, new outbound transport, open relay, SASL activation, expanded destinations, catch-all, bare reply address, invalid UID/GID and unsafe file roots.
- `tests/test_probe_owned_postfix_staging.py` checks temporary file owner-only mode, deterministic manifest, default zero effects and Founder status non-authority.
- **Final JEV, CRM, Conversation OS, Postfix staging and research regression: 808 passed, 10 subtests passed, zero failures, 1 pre-existing Starlette/AnyIO deprecation warning**. Python syntax and diff checks passed; frontend TypeScript validated with `tsc --noEmit --incremental false`.
- Founder JEV status and standalone page indicate a prepared offline profile but NOT validated SMTP acceptance, production Postfix reception or signed original buyer receipt.
- Reuse Wave 11 source-truth gate and Wave 12 signed-receipt fixture; neither is implicitly promoted by this work.

## Next exact production readiness steps

1. Coordinate a single mail-system owner and a separate isolated receiving environment; check host ownership, inbound TCP/25 reachability and provider restrictions. Current DNS must not be changed until independent original-message delivery plus rollback works.
2. Provision Postfix with an actual unprivileged OS `postfix` account and approved immutable config, UID/GID mailbox owner and spool locations; run `postconf`, `postmap`, and verified exact-recipient RCPT tests **inside an isolated host/container**, not on the production mail route.
3. Test that unknown recipients, root-domain recipients, unauthenticated external relays, wildcard recipients and missing aliases are rejected **at RCPT**, so no backscatter/catch-all can occur.
4. Independently implement audited trusted SMTP sender authentication with DKIM/SPF/DMARC alignment at the MTA trust boundary, including quarantining forwarded/ambiguous mails and attached content. A user-supplied `Authentication-Results` header must never be trusted.
5. Wire original MTA queue/spool and raw-message digest with owner-restricted proof to Wave 12 signer; provide separately verified canonical tenant/intent bindings and suppression, without private key access from JEV or HTTP.
6. Run controlled inbound proof on a separately authorized testing route. Prove bounce and retry recovery, idempotency, observability, privacy retention, and safe fallback before considering an MX cutover.
7. Founder separately approves any Postfix install, network listener, signed production key, DNS/MX change, mailbox migration, migration 051, outbound release or production deployment.

No real buyer reply, real contact identity, signed original SMTP delivery, recognized revenue, or production receiving service was authenticated in this wave.

## Official technical references

- Postfix `postconf(5)`: https://www.postfix.org/postconf.5.html
- Postfix Virtual Domain Hosting: https://www.postfix.org/VIRTUAL_README.html
- Postfix `virtual(5)`: https://www.postfix.org/virtual.5.html

No upstream code was copied; the staging generator is EmpireOS first-party code.
