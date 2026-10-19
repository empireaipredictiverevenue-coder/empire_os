# Empire AI Predictive Intelligence flagship — open-source evaluation and customer experience

19 October 2026 | Owner branch: feature/predictive-decision-control-20261018
Cross-product impact: Diagnostic, Command Center, Intelligence OS,
Autonomous OS, Strategic Private, data products and self-serve portal.

## Why these four (and what we can truthfully say)

A flagship customer must understand its verified opportunities, blocked
commercial facts, original proof, next recommended action, time-to-value
and *actual realised result*. Observability cannot turn an AI guess into a
buyer, a source signal into a conversion, or a forecast into a settled sale.

This wave adds **integration interfaces and offline evaluation** to the
EXISTING EmpireOS ecosystem. It does not deploy third-party platforms, load
third-party scripts on customers' browsers, install heavy containers, move
customer/tenant data to vendors, or override EmpireDB governance.

| Component | Existing integration / this wave | Activation status |
|---|---|---|
| Evidently | New optional offline bounded-category quality evaluator; typed source quality deltas, optional `Report(DataDriftPreset())` on explicitly supplied safe aggregates. Scientific Agent/Quant remain authoritative. | Optional scientific evaluation dependency declared in `pyproject.toml`; NOT installed in production; no remote upload. |
| Langfuse | Existing `empire_os/otel_telemetry.py` supports Langfuse OTLP. New `emit_flagship_quality_trace` uses its existing provider-neutral `TelemetryEvent` with ONLY fixed enum statuses and bounded duration. | Tests verified local event; remote OTLP exporter NOT enabled by this wave. |
| PostHog | New Next.js `captureFlagshipUxEvent` interface accepts only fixed actions/results and requires manual events, connected SDK, explicit user consent and tenant authority. Does not accept URLs, names or user-supplied event properties. | No SDK loaded/installed; autocapture, pageviews, flags, remote events and recordings OFF. |
| OpenReplay | New `startFlagshipReplayForApprovedDiagnostic` facade requires explicit per-session consent, tenant auth, owner approval, successful redaction test, licence obligations, retention/deletion policy and no sensitive field capture. | No SDK loaded/installed; session replay OFF. |

### Open-source upstream and fork ownership

- Evidently: https://github.com/evidentlyai/evidently — Apache 2.0.
- Langfuse: https://github.com/langfuse/langfuse — core MIT; enterprise
  code uses separate terms. Existing OTLP integration means **no fork
  necessary** just to send traces.
- PostHog: https://github.com/PostHog/posthog-foss — MIT, no proprietary
  `ee/`; official repository is a read-only auto-updating mirror.
  Use the separately maintained JS SDK once the authorized frontend owner
  approves it. **No full PostHog fork or hosted deployment needed** simply
  to capture manual events.
- OpenReplay: https://github.com/openreplay/openreplay — most code AGPLv3,
  some MIT, and `ee/` under separate licence. Legal/operational obligations,
  consent, recording storage, deletion and masking must be reviewed before
  hosting or modifying a fork. **No OpenReplay fork deployed**.

**FORK STATUS: NONE CREATED.** The connected GitHub account has repository
access but its available tool actions do not include GitHub's `forks` API;
the server has no `gh` CLI. A GitHub fork is a separately verifiable repo,
not an alias for importing a dependency or copying code. Before forking,
check existing owner forks and the exact need to modify upstream code.
Prefer maintained pinned upstream packages and tight Empire-owned adapter
contracts. Future forks should remain in the `empireaipredictiverevenue-coder`
GitHub ownership boundary and record an actual fork URL and upstream SHA.
Do not fork full 100MB+ analytics monorepos or add separate databases to
`/srv/empire_os` merely for vendor-name coverage.

## Product-to-component roadmap

### Wave A: source and scientific credibility (highest value)

The **Predictive Revenue Diagnostic** uses the existing source/funnel gap
register, typed evidence pathways and the new offline Evidently-compatible
quality interface. Real baseline and current samples with population scope
and sufficient statistical power must be collected before any drift verdict.
Drift flags require human investigation, and prospective held-out labels
are required before model forecast error can be measured.
**Customer experience:** explain “data observed / data missing / next proof”
and provide diagnostic recommendations that cite original evidence.

### Wave B: enterprise control / scientific agent quality

The **Command Center** and **Intelligence OS** use existing OTel to connect
ASTRA stage traces, source retrieval outcomes, original model proposals and
evaluation status. Langfuse may be added as a backend exporter only after
the owning team verifies GDPR/UK data flow, redaction, tenant-bound trace
access, retention and budget. Never log full prompts with buyer, health,
payment or confidential contract terms. Use aggregated bounded evaluation
events where possible.
**Customer experience:** reproducible reasons for recommendations, clear
statuses, independently verified results vs forecasts.

### Wave C: customer self-serve conversion UX

For the **self-serve and white-label portal**, trial a first-party
manual-event taxonomy: `results_viewed`, `evidence_explanation_opened`,
`next_action_viewed`, `first_verified_result_observed`,
`unsupported_result_reported`. PostHog receives only these fixed labels
under explicit analytics consent, authenticated tenant authority,
redaction and approval. Measure task success, time to first verifiable
outcome, correction rate and user comprehension—not clicks for vanity.
Start local/first-party testing before any paid service or cloud export.

### Wave D: optional troubleshooting sessions

For **Autonomous OS and private strategic customers**, make OpenReplay
an opt-in troubleshooting tool for an isolated support session, never a
blanket recorder. Mask email, phone, passwords, payment terms, authentication
tokens and CRM notes and verify masking in the *actual browser rendering*.
Set short retention and fulfil access/deletion obligations; review AGPL
network-use obligations and the enterprise code boundary. Consider whether
PostHog session replay already solves the needed task before ever deploying
OpenReplay. Don't run two recorders on the same confidential screen.

## Feature files, tests and safe commands

- `empire_os/flagship_quality_integrations.py`: optional Evidently offline
  evaluation; data-status distribution preflight; narrow OTel trace event;
  vendor readiness for all four.
- `apps/search-command-centre/src/lib/flagship-experience-adapters.ts`:
  PostHog manual capture and OpenReplay diagnostic start contracts.
- `empire_os/predictive_decision_control.py`: adds
  `flagship_quality_integrations` to the existing founder-only read API.
- `apps/search-command-centre/src/app/founder/page.tsx`: read-only
  integration readiness surface. Not a customer-tracking script.
- `scripts/review_flagship_quality_integrations_20261019.py`: by default
  only reports status; with two explicitly supplied private aggregate files,
  runs optional offline Evidently on bounded cohort categories; never
  processes unredacted buyer records or uploads the report.
- `pyproject.toml`: adds isolated `scientific-evaluation` optional extra,
  not a base dependency or production installation.

Read-only:
```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_flagship_quality_integrations_20261019
```

Targeted tests:
```bash
PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -m pytest -q \
  tests/test_flagship_quality_integrations.py tests/test_founder_dashboard.py
cd apps/search-command-centre
./node_modules/.bin/tsc --noEmit -p tsconfig.json
./node_modules/.bin/eslint src/app/founder/page.tsx \
  src/lib/founder-api.ts src/lib/flagship-experience-adapters.ts
```

## Remaining before “fully integrated” can be claimed

1. Establish approved upstream versions and codeowners; install Evidently
   only in an **isolated scientific runner** with a dependency/size review;
   verify its real Report output on a genuine (lawfully sampled) reference
   and current cohort, then map results into existing Scientific Agent.
2. Review existing OTel traces and scrub ALL sensitive tags. Connect a
   self-hosted or approved Langfuse OTLP endpoint and verify actual receipt
   only with synthetic/no-personal-data events before production data.
3. Connect PostHog's pinned JS SDK to a consent-aware authenticated tenant
   portal component. Verify both no-consent = zero external requests and
   consent-withdrawal = disabled. No autocapture or recording by default.
4. Run OpenReplay redaction + AGPL/privacy/tenant pilot, or decide it is
   duplicative of PostHog replay and don't deploy it.
5. Connect proper authenticated customer result receipts to product cards
   before highlighting financial ROI. Customer cannot see another tenant's
   data, even if a vendor dashboard shares instrumentation.
6. Respect production multi-agent ownership. Merge/release backend and UI
   from this feature branch together; no live site/deployment change here.

No actual vendor fork, external customer telemetry, deployed SDK, new
production service, billable spend, payment or CRM mutation in this wave.
This is meaningful code-level staging and offline capability—not a claim
that external platforms are operational or that customers are being tracked.
