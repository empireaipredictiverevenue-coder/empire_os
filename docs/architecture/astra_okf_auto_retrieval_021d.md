# Astra OKF automatic evidence retrieval — 021D

## Outcome
The existing Astra **department dispatch** service now consults the newest
private OKF bundle automatically, but ONLY when an *already admitted* task has
an exact, structurally supplied company identity and an explicitly allowlisted
evidence-research action. No additional timer, daemon, paid provider, third-party
database or outbound sender is installed.

Retrieval happens **after** the existing DepartmentWorkQueue decisions and
produces advisory data in `okf_research_advisory` only. It does not affect the
step's authority, priority, queue state, worker adapter, skill approvals,
payment/terms governance or dispatch list. The existing explicit
`--okf-bundle` option remains supported and takes precedence.

## Exact-match retrieval
Eligible target/action combinations are a short allowlist in
`empire_os/astra_okf_auto_retrieval.py`, initially covering the existing
identity, buyer review, buyer capacity, search and intelligence evidence lanes.
Only `intelligence_request` and `memory_query` fields
`company_domain`, `buyer_domain`, `company_website` and `website` may
identify a company. Multiple supplied identities must agree exactly.
Natural language descriptions, opportunity text, skill instructions, email
patterns, website aliases and name similarity cannot establish identity.

The newest `runtime/knowledge/okf_private/run-*` bundle must be from the last
48 hours (within five minutes of server clock skew). Its complete Markdown
inventory must match the checksum manifest; symlinks and unmatched files are
blocked. Only concepts with matching company domain, fresh first-party source
URLs and `trust: unverified` can enter the advisory output.

Limits: 128 visible bundle entries; 30 candidate records read; 30 eligible
plan steps scanned; five matching references maximum; three URLs per match.
If nothing matches, research is omitted or the receipt gives a bounded
unavailable/no-current-evidence status. Stale claims are never silently
promoted to current trust.

## Agent usage
Astra departments **receive source references**, not page prose or instructions.
A retrieval record supplies `step_id`, `concept_id`, `source_urls`,
`observed_relationship`, `fresh`, `trust: unverified` and
`execution_authority: none`. No automatic document or task execution
occurs. Other agents can also call the same pure, read-only retrieval helper
with their already-authorised structured work item; no new agent or clock loop.

**Important:** this does not create verified buyer demand, named contact
personhood, consent or a payment. Source hashes establish local integrity,
not independently signed proof of publication. An honest failure to find an
exact scoped identity must remain `no_relevant_company_bound_task`.

## Production safety
Do **not** manually run `dispatch_astra_departments.py` against production
just to preview retrieval: the existing dispatcher can enqueue internal work.
Test the pure function on the latest existing private bundle or use a temporary
repo containing a synthetic plan.

Validation: focused adversarial manifest, role, identity, stale/future clock,
missing bundle, authority gates, duplicate queue and runtime tests.
No new database migration, raw outbound, privileged actions or service restart.
