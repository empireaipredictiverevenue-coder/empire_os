# EmpireOS Jev — guarded client-pain discovery activation

**21–22 October 2026.** Owner-approved read-only production observer.
**Deployment commit** `6e9b1febb`, with detector follow-up `ad8275fb5`
and membership/legal pain review refinement (see later branch history).
Existing canonical database: **EmpireDB PostgreSQL**, no new SQL access.

## Installation and exact authority boundary

The operator left the production collector, its uncommitted MiniMind work,
and the other active production modifications intact. Released only two
additive files:

- `/srv/empire_os/empire_os/jev_client_pain_discovery.py`
- `/srv/empire_os/scripts/run_jev_client_pain_observer_20261022.py`

Enabled user-scope `empire-jev-client-pain-observer.timer` and
`empire-jev-client-pain-observer.service` on a 15-minute cadence.
The service is a local source reader, never a crawler. It reads the existing
community history and unresolved *social intent only* from the existing
canonical signal inbox. Permits and litigation/court observations are
excluded. The service uses production Intent Brain + JEV and a bounded
detector with no hosted provider.

Derived receipts:
`/srv/empire_os/runtime/jev_client_pain_discovery/aggregate_latest.json`
and `private_latest.json`; private directory mode 0700, files mode 0600.
The aggregate contains no direct source URLs, post text, names or contacts.

A zero-write dry run was completed first. One-shot scheduled service
returned `Result=success`, `ExecMainStatus=0` on the first activation.
No model API, outbound, CRM writes, database writes, payments, scraping or
new canonical prospects are performed by the observer.

## Public source rotation expansion

Added public Reddit research subreddits for `Dentistry` and `SaaS` to
the existing ICP source atlas. The existing one-feed-per-15-minute-cycle
collector design is preserved. UK `smallbusinessuk`, US `LawFirm`,
roofing, solar, HVAC and agency sources already exist. Access blocked or
rate-limited by upstream platforms must remain a source-health error, not
a false statement that demand is zero. These sources are NOT permission
to message subreddit participants.

The production source atlas was checked against a known SHA256 before
its **only** in-place replacement and its original contents were saved.
The production collector file was NOT overwritten or committed.

## Initial commercial truths

The first live pass processed 46 source records (11 community + 35
canonical unresolved social-intent records); after link deduplication,
12 source observations contained a broad topic or specific pain expression.
None met a specific pain-expression review threshold. The earlier generic
identity-review signal was downgraded by the later rule requiring an
explicit pain expression. No verified qualified prospects or payable leads.

A separate manual public-source research review used six links observed
in public forum pages. It identified specific hypotheses in four thematic
buckets: SaaS first-user acquisition, dental marketing-return uncertainty,
UK membership acquisition, and PI legal lead quality. One UK source explicitly
stated it was not seeking a solution and is marked NO_SOLICITATION; a dental
source also explicitly barred solicitations. One discussion was routed
for pain hypothesis review, not company identity promotion or contact.
These manual research notes are only in separate, 0600 private files and
were NOT inserted into production canonical signals.

Public research URLs used in that separate manual review:

- https://www.reddit.com/r/SaaS/comments/1x9ic54/i_built_a_real_saas_product_but_im_struggling_to/
- https://www.reddit.com/r/Dentistry/comments/1x47h11/marketing/
- https://www.reddit.com/r/smallbusinessuk/comments/1wcvn2u/tough_year_in_business_2026/
- https://www.reddit.com/r/LawFirm/comments/1u19qb0/advice_for_a_2monthold_pi_solid_on_leads_and/
- https://www.reddit.com/r/LawFirm/comments/1vz3690/new_law_firm/
- https://www.reddit.com/r/Dentistry/comments/1x7nn42/need_help_with_selecting_a_marketing_company_as_a/

## Production rollback and independent verification

Guarded backup/release:
`/home/ubuntu/empire_releases/jev_client_pain_guarded_20261022_6e9b1febb`

To disable and roll back **only this release**, run as `ubuntu`:

```bash
bash /home/ubuntu/empire_releases/jev_client_pain_guarded_20261022_6e9b1febb/rollback.sh
```

The rollback disables the observer, removes only its two new production
files and its user units, and restores the exact pre-release source atlas.
It does not delete private evidence receipts or reset any other agent's
changes. Verify post-rollback source hashes before considering a rerun.

**Future integration gate:** Surface private queue only in the authenticated
Founder Console with tenant/suppression boundaries, after independent
Research/Buyer Scout proof of source rights, first-party identities, current
need and explicit contact permission. Do not merge the modified community
collector blindly: it has a separate active MiniMind integration.
