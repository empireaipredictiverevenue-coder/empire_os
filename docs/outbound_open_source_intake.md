# Empire Deliverability Open-Source Intake

## Adopt now

### checkdmarc — Auth Observer
Purpose:
- validate SPF and DMARC
- DNSSEC checks
- MX/STARTTLS checks
- MTA-STS and TLS-RPT
- BIMI validation where relevant
- machine-readable JSON/CLI output

Integration:
- wrap as evidence producer for Empire Auth Observer
- persist observations in canonical deliverability evidence
- never let its output bypass Ringleader policy

License: Apache-2.0

### parsedmarc — DMARC Intelligence
Purpose:
- ingest DMARC aggregate and failure reports
- ingest TLS-RPT
- parse Gmail/API/IMAP mailboxes where needed
- export structured evidence

Integration:
- route parsed results into Empire canonical telemetry
- calculate authenticated source inventory and unknown-source drift
- feed Ringleader domain/auth risk

License: Apache-2.0

### DNSControl — Domain Sovereignty
Purpose:
- DNS as code
- provider portability
- Cloudflare and many other provider integrations
- reviewable preview/push workflow

Integration:
- canonical source of desired DNS state
- PR-reviewed DNS changes
- zone backup and provider migration support
- Ringleader only consumes status; DNS mutation remains approval-gated

License: MIT

### Rspamd — Local preflight/scoring engine
Purpose:
- message analysis and spam scoring
- DKIM/SPF/DMARC-aware processing
- URL and content rules
- programmable Lua extensions

Integration:
- use as a local advisory signal before outbound
- never treat its score as proof of Gmail/Outlook inbox placement
- expose score/reasons into Empire message evidence

License: Apache-2.0
Note: some Rspamd-hosted data services have separate fair-use terms.

### Mailpit — deterministic dev/test mail sink
Purpose:
- capture SMTP traffic in development
- inspect MIME, headers, HTML, links and attachments
- API-driven integration tests

Integration:
- production-safe test harness
- no real external delivery
- test the governor, transport adapters and event pipeline

License: MIT

## Benchmark before adoption

### Stalwart
Potential use:
- Empire-controlled seed/test mailboxes
- sovereign inbound mail
- SMTP/IMAP/JMAP infrastructure
- authentication-aware mail services

Why benchmark:
- modern Rust architecture and broad protocol support
- AGPL-3.0 / commercial licensing requires deliberate review
- not necessary for Ringleader core

### Postal
Potential use:
- Empire-owned outbound/transactional transport adapter
- self-hosted sending/receiving platform

Why benchmark:
- open-source SendGrid/Postmark-like transport
- MIT license
- transport sovereignty benefit
- self-hosted sending reputation, rDNS, IP reputation and abuse operations remain substantial operational responsibilities

## Do not adopt as core

### Mautic / list-style marketing automation platforms
Empire already owns:
- targeting
- campaign decisions
- outreach governor
- suppression
- buyer intelligence
- Predictive Revenue
- learning loop

Use only for comparative research if needed; do not make them authoritative.

## Target architecture

DNSControl
   -> Empire Domain Sovereignty Observer
checkdmarc
   -> Empire Auth Observer
parsedmarc
   -> Empire DMARC Intelligence
Rspamd
   -> Empire Message Preflight
Mailpit
   -> Empire Test Harness
Stalwart/Postal
   -> optional transport/seed adapters

All signals
   -> Ringleader
   -> Outbound Governor
   -> READY / LIMITED / REMEDIATE / HOLD
