# Empire AI — TREG & Listmonk Recovery

**19 October 2026 | Unified Lead Intelligence owner | feature branch only**

## A. Production inspection: what exists

- Canonical application/repository: `/srv/empire_os`, self-hosted
  EmpireDB PostgreSQL. Do **not** use Supabase or create a competing
  customer database.
- Old Listmonk assets are recoverable as Git historical code:
  - `f6038ca1:empire_os/listmonk_import_leads.py`;
  - `8dc9c512:empire_os/listmonk_bulk_campaign.py`;
  - `8dc9c512:empire_os/smtp_brevo_relay.py`.
- **Listmonk is NOT live or confirmed restored:** no current
  `listmonk` command, no 127.0.0.1:9000 listener, no observed systemd
  Listmonk service. The current Ubuntu account cannot query the root
  Docker daemon or inspect restricted PostgreSQL database/volumes.
- Old commit messages mention ~628–629 `Empire Leads` records. That is
  a *historical report only*, NOT a current database count, marketing
  opt-in proof, saleable buyer stock or an authorised contact list.
- Old relay and bulk campaign code had the ability to send through a
  third-party email service. **DO NOT RESTART/IMPORT** these old scripts
  without reviewing their licensing, consent, unsubscribe/bounce sync,
  suppression and existing sender authorisation. No mail was sent
  during this recovery evaluation.
- Legacy authentication material was previously recorded in Git
  history. It is considered exposed: **rotate all historical Listmonk
  admin and SMTP relay credentials**, do not reuse old values. A code
  file or Git log must not be treated as a credential vault.

## B. Safe path to restore the *existing* Listmonk instance

1. Privileged service owner inventories existing root Docker containers,
   volumes, image and original Postgres DB (read-only) and checks local
   encrypted logical/offsite recovery artifacts. Preserve originals and
   perform any restore in an isolated, namespaced environment. Do not
   create an empty replacement advertised as restored legacy data.
2. Use currently supported Listmonk release/documented config rather
   than blindly running old container images. Keep private loopback-only
   access until identity, DB schema, current audit and backup complete.
3. Rotate all Listmonk credentials and sender keys. Start with SMTP
   disabled; do not enable a public newsletter form or automated
   campaign, and do not grant ASTRA/B2B outbound agents permission to
   write to subscriber/campaign endpoints.
4. Read-only compare (using protected owner credentials) original
   subscriber **counts** and list memberships against any recovered
   backup. Do not export private subscriber emails into an unsecured
   file, ChatGPT log or public dashboard.
5. Distinguish legacy cold B2B prospect rows from legitimate
   newsletter opt-ins. Require verifiable double opt-in, marketing
   purpose, a current unsubscribed/bounce/opt-out state, and canonical
   CRM/EmpireDB suppression. No mass import of historical scraper or
   Buyer Network contacts without this evidence.
6. Exercise authenticated private `GET /api/lists`,
   `GET /api/subscribers` and `GET /api/campaigns` checks with
   a *fresh, least-privilege Listmonk credential* in the owner
   environment. Campaign creating/sending, transactional HTTP
   endpoints and old relay scripts remain unapproved.
7. Publish a fresh founder read-only subscriber/list count *only after*
   the source and rights audit. Never interpret counts as emails sent,
   paid customers, active buyer capacity or canonical Exchange stock.

Owner-only suggested read-only inventory (not run by this build):

```bash
# Run only within the authorised root/ops console.
sudo docker ps -a --no-trunc
sudo docker volume ls
sudo systemctl list-unit-files '*listmonk*' '*smtp*relay*'
# Do not paste secrets or full container environment into chat.
```

## C. TREG repo fit and deployment boundaries

Repo reviewed: https://github.com/superdesigndev/treg

It exposes a third-party catalog and gateway for read-only web
extraction/search, company enrichment, SEO keywords, backlinks, and
lead-signals. It can proxy paid provider calls, upload local secrets,
run registered CLIs and skills. It is not a replacement for:
`EmpireDB`, canonical CRM suppression, approved first-party
Search Intelligence, our Scrapling source controls, or our existing
Waterfall. The repo's hosted gateway is outside EmpireOS data custody.

**Implementation added:** `empire_os/treg_source_policy.py` is the
single preflight for proposed capabilities. Default is **zero spend**,
zero credentials, no network, source rights and third-party
processing NOT preapproved, and no customer data transfer. It
refuses consumer/claimant/patient/person-enrichment and mass outbound.
Even a successful policy review does not execute a provider request.
No `curl|sh` install, TREG token setup or `treg upload` was run.

Manual source classification remains separate: any new vendor data
must meet source terms, provenance, company/territory identity,
non-PII restrictions, and then independent canonical EmpireDB
read-only identity lookup. Vendor scores are NOT buyer intent.

## D. Implemented & verified

- `empire_os/listmonk_recovery_boundary.py`: original Git
  component and localhost-port inventory; conservative audience
  consent/suppression classification, aggregate-only outputs.
- `scripts/review_treg_and_listmonk_recovery_20261019.py --read-only`:
  no secrets, mail sends, external paid calls or DB changes.
- `GET /v1/founder-lead-supply/marketing-tooling`: code only,
  **staged private Founder route**, not independently deployed.
- All tests isolated against fixtures with no sender/network
  side effects, including hardholds on missing double opt-in,
  suppression status, paid TREG calls, invalid price and sensitive data.
- Operational result (19 October): **historical code recoverable;
  Listmonk subscriber DB NOT verified**. TREG reviewed as an optional
  provider, no money or data transferred.

**Production approval gates:** privileged read-only Docker/DB recovery
inventory first; explicit owner approval for data restore, service
installation/restart, credential rotation and marketing list import.
Email sends remain individually and legally approved actions, not
part of this recovery.
