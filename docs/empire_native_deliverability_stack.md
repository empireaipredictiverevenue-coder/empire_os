# Empire Native Deliverability Stack

## Doctrine

Empire owns the deliverability control plane.

External providers may transport mail or expose network-specific reputation evidence, but
EmpireOS owns:

- recipient verification state
- sender/domain inventory
- SPF/DKIM/DMARC/TLS evidence
- bounce classification
- suppression state
- sender reputation scoring
- pacing and daily-cap decisions
- first-touch content safety checks
- delivery health windows
- inbox-placement measurements
- alerts and fail-closed decisions
- audit history

No provider dashboard is authoritative. Provider APIs and webhooks are evidence sources.

## Vendor categories replaced by Empire

### 1. Email verification SaaS -> Empire Recipient Verifier

Inputs:
- syntax validation
- DNS/MX existence
- historical delivery evidence
- previous hard/soft bounces
- suppression history
- domain catch-all confidence
- person/company identity binding

Output:
- VERIFIED
- RISKY
- UNKNOWN
- INVALID
- SUPPRESSED

Do not rely on SMTP VRFY as canonical evidence; many providers disable or tarp it.

### 2. Warm-up SaaS -> Empire Reputation Ramp Controller

Empire will not create synthetic engagement or fake reply networks.

Instead it will:
- ramp real/consented traffic gradually
- prevent sudden volume spikes
- isolate transactional and promotional identities
- monitor bounce/complaint trends before increasing volume
- reduce or halt volume automatically when health worsens

### 3. Inbox-placement SaaS -> Empire Seed Placement Lab

Use mailboxes controlled by Empire across supported mailbox providers.
For controlled test messages, measure:
- inbox / primary placement
- spam/junk placement
- missing/rejected
- latency
- authentication results
- provider-specific headers when available

Placement is separate from provider "delivered" status.

### 4. Sender reputation SaaS -> Empire Reputation Model

Merge:
- 1d / 7d / 30d delivery health
- permanent and transient bounce rates
- complaints
- suppressions
- delayed and failed deliveries
- Gmail Postmaster domain reputation / spam / delivery errors
- Microsoft SNDS/JMRP evidence when available
- DMARC aggregate reports
- DNS/authentication state
- placement-lab results
- sender-volume changes

Output:
- GREEN
- AMBER
- RED
- HOLD

### 5. DNS/authentication SaaS -> Empire Auth Observer

Continuously verify:
- SPF
- DKIM
- DMARC
- alignment
- MX
- PTR/rDNS where Empire owns the sending IP
- TLS readiness
- policy changes
- DMARC rua aggregate reports

### 6. Cold-email sequencer -> Empire Outbound Governor + Scheduler

The existing Phase 3E outbound governor remains the authority.
Routing must never override:
- suppression
- evidence readiness
- provider-policy compatibility
- sender health
- daily caps
- contact confidence
- decision-maker binding
- founder/live-send approval gates

### 7. Bounce/suppression SaaS -> Empire Delivery Evidence Store

All provider events are normalized into canonical outcomes:
- SENT
- DELIVERED
- DELAYED
- SOFT_BOUNCE
- HARD_BOUNCE
- COMPLAINT
- SUPPRESSED
- FAILED
- RECEIVED_REPLY

Permanent bounce and complaint events immediately affect future eligibility.

## Current evidence

The current Resend adapter is only a telemetry source.
Empire's own rolling health service consumes provider metrics and exposes its result via:

    GET /v1/founder-outbound-deliverability

Future adapters feed the same health model instead of changing the decision logic.

## Production gates

A sender is not eligible for production use unless:

1. provider policy permits the traffic type
2. authentication/alignment is verified
3. recipient quality evidence is present
4. suppression state is known
5. bounce/complaint health is inside Empire limits
6. volume ramp is inside policy
7. content passes the first-touch lint
8. the existing outbound governor approves the commercial intent

## What Empire cannot replace

Empire cannot replace the destination mailbox networks themselves.
Gmail, Outlook, Yahoo and other recipient systems decide final filtering.

Empire can, however, own the collection and interpretation of every signal those networks
make available and use controlled test mailboxes to measure actual placement.
