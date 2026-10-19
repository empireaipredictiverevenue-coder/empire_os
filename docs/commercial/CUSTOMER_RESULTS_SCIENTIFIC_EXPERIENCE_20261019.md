# EmpireOS Customer Results Experience: Verified Value Before Vanity Metrics

19 October 2026 | Branch feature/predictive-decision-control-20261018

## Objective

An excellent customer experience is not merely a cinematic portal or more
model features. Each customer should see:
1. What EmpireOS has **observed** (source and date).
2. What is **inferred or projected** (uncertainty, model and assumptions).
3. What has been **independently verified** (identity, payment, delivery,
   acceptance, and actual realised customer outcome).
4. Exactly **which one fact is missing** and who should act next.
5. When the last verified customer outcome occurred, and when it was
   refreshed; never invent a revenue claim.

The canonical EmpireDB and existing ASTRA, CRM, Quant Brain, Economic Memory,
Search Intelligence and OTel foundation must be reused. We deliberately
avoid cloning those services or adding an additional database.

## Important original trust gap

The existing `POST /v1/revenue-crm/customer-success/preview` accepted a
user-supplied buyer_id, booleans claiming payment_verified/fulfilment_delivered
and user-supplied evidence refs and timestamps. The route correctly provided
internal read-only retention/expansion triage, but that result is NOT
independent proof. Clients must not treat `available=true` in this
**preview** as a genuinely verified customer or earned revenue.

### Code delivered

- `empire_os/revenue_crm_customer_results_experience.py` is a pure,
  deterministic results/next-action review. It composes the existing
  `RevenueCrmRetentionEvidence`, `RevenueCrmRetentionFreshness` and
  `CustomerSuccessReviewRoute` contracts; it does not invent a second
  source of truth.
- The same CRM preview route now returns the backward-compatible
  `customer_success` plus `customer_results_experience`, containing
  five labelled milestones: buyer identity/scope; payment; fulfilment;
  customer outcome; current service capacity.
- Each milestone distinguishes preview-reported, missing, stale,
  unverified unsuccessful and blocked source states. The first outstanding
  stage yields a specific human-readable action.
- Even a request with every boolean set true returns:
  `independently_verified_milestone_count=0`,
  `verified_customer_outcome=null`,
  `verified_realized_revenue_cents=null`,
  `verified_customer_roi=null`,
  `customer_visible_proof_authorized=false`.
- Buyer IDs, names, raw payment references, addresses and customer contacts
  are never included in the new result projection. There is no query, API
  send, model call, CRM mutation, payment, economic memory or outbound.
- No new public customer endpoint has been created. This is a read-only
  **request-assertion preview** contract; verified customer data must come
  later through authenticated tenant-specific EmpireDB readers and
  reconciliation, with an entirely separate proof state.

### Required production/customer portal UX

For authorised users only:
- Display stage and freshness + evidence class, with contextual explanation.
- First actionable next step, owner and whether founder approval is required.
- No zeros when a source is unavailable; distinguish UNKNOWN, NONE
  VERIFIED and VERIFIED ZERO.
- Keep the same fixed definitions of qualified lead, enquiry, accepted
  offer, payment, fulfilment, customer outcome, realised revenue, and ROI.
- Show sample/modelled figures separately from customer-specific actuals.
- Add a user-facing "Report an incorrect result" route later, bound to the
  authenticated tenant and reviewed by Customer Success (not direct model
  training or automated refund/compensation).
- Run accessibility/mobile checks before any customer-facing release.

## Open-source evaluation: adopt in stages

No new dependency has been installed or external telemetry activated.

### 1. Evidently (github.com/evidentlyai/evidently)

PREFERRED scientific evaluation library for offline data drift, null rates,
source freshness, distribution shifts and eventual actual prediction
performance. Use only on privacy-safe aggregates and prospectively
timestamped, matched outcomes. Start with an offline adapter that compares
reference and current cohorts. A drift alarm is not proof of forecast
inaccuracy, and p-values must not be reported without sample assumptions.
Existing `lead_shadow_calibration_benchmark` and Quant Brain remain the
canonical decision/outcome evaluators.

### 2. Great Expectations GX Core (greatexpectations.io)

Useful for explicit validation expectations on imported source feeds
(schema, ranges, null limits, allowed licence, cardinality and duplicates).
The existing Python source validators already cover some of these
requirements. Only adopt selected contracts where offline tests show a
real benefit and licence/dependency/compute overhead are acceptable.
Do not use a full new deployment stack for a dozen feed checks.

### 3. OpenLineage (openlineage.io)

Optional portable run / job / dataset metadata format for tracing which
source, transform and timestamp fed a customer result. Map existing EmpireOS
evidence references to dataset and job facets only if the mapping is exact;
never invent lineage links by joining all inputs to all outputs.
Do not deploy Marquez, Kafka or a second metadata DB just to pilot this.

### 4. OpenTelemetry + Langfuse (already integrated, optional exporter)

The repository already contains `empire_os/otel_telemetry.py` with optional
OTLP/Langfuse support and best-effort local events. Reuse it to trace:
source ingest → scientific eval → ASTRA worker → held/unheld proof →
customer-result render. Redact data, tenant identity, prompts and secrets
by default; remote emission needs explicit data-protection sign-off and
£0 cost policy. Do not install an entirely new Langfuse integration.

### 5. OpenFeature / PostHog / OpenReplay (product UX improvements)

OpenFeature is a vendor-neutral flag API; useful later for tenant-based
feature previews and safe canary releases. This requires authenticated
server-side tenancy, not client-supplied tenant IDs.

PostHog supports funnels, feature flags, surveys and session replay;
OpenReplay focuses on private self-hosted session replay, debugging and
co-browsing. They can diagnose onboarding friction and user confusion, but
session replay may capture sensitive CRM data. Do not enable recording,
pixels, client analytics or remote processing without lawful consent,
appropriate redaction, documented retention and funding approval.
Measure task completion and time to first useful verified opportunity
before introducing heavyweight analytics.

Sources reviewed 19 October 2026:
https://github.com/evidentlyai/evidently
https://docs.greatexpectations.io/docs/core/introduction/
https://openlineage.io/docs/client/python/
https://langfuse.com/docs/observability/overview
https://openfeature.dev/docs/reference/sdks/server/python/
https://github.com/posthog/posthog
https://github.com/openreplay/openreplay

## Scientific CX scorecard to implement after real rollout

Track with time periods, bounded cohorts and tenant consent:
- Time-to-first independently verified customer-relevant insight.
- Fraction of opportunities with original source lineage and complete
  provenance, and fraction with rejected or disputed evidence.
- Buyer-approved offers per actually verified buyer conversation.
- Settled, fulfilled, recognised revenue and true variable cost.
- Cohort-calibrated Brier score vs historical base rate ONLY when
  original prospective predictions and future verified outcomes exist.
- User comprehension/task success in a mobile usability test.
- Incorrect-result reports and subsequent resolution time.

Do NOT optimise vanity total signals, speculative buyer seats,
demo gross revenue, unsourced ROI, or model-confidence percentages.

## Tests / release boundary

The feature branch includes isolated tests for all-true forged preview
input, payment missing, unsuccessful outcome, stale evidence, mismatched
buyer identity, API backwards compatibility, no leak of private refs,
and no verified revenue claim. Broad CRM + Predictive Revenue regressions
were checked.

Production DB, other agents, paid provider routes and public site are
unchanged. Customer-facing portal activation will require coordination
with owning CRM and authenticated tenant UI agents. Never use client
supplied preview evidence to compute public/tenant verified revenue.
