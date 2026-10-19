# Empire AI flagship — real longitudinal source-quality baseline V1

19 October 2026 | Branch `feature/predictive-decision-control-20261018`

## What was missing

The staged Evidently integration could compare supplied categorical
counts, but there was no original reference observation linked to our
ACTUAL canonical Source Intelligence. Inventing a historical baseline
from today's data or grouping repeated copies of the same four source
adapters would make a scientific drift result meaningless.

This release establishes the first REAL source-quality baseline and a
strict, privacy-safe path for future comparisons. It deliberately does NOT
pretend that statistical drift or forecast accuracy has been validated.

## Data pathway now implemented

```
Canonical existing acquisition + Opportunity Factory + Quant + competitor
       ↓ read-only canonical revenue_stream_mining validation
Fixed four source statuses, lineage fingerprints, no raw contacts
       ↓ manual explicit baseline capture into private feature worktree
Local append-only JSONL with ordered timestamps + SHA-256 chain
       ↓ read-only Founder Decision Control scientific_source_history
Baseline health, real category counts, next internal evidence action
       ↓ after genuinely later observation at least 24 hours apart
Descriptive status change ONLY, no p-value / causal effect / ROI claim
       ↓ once independent cohorts and outcomes actually exist
Evidently evaluation + prequential Quant/Economic Memory validation
```

### Science / privacy

- Source statuses: FRESH/OBSERVED → OBSERVED; STALE → STALE;
  MISSING → MISSING; invalid, untrusted and future → HELD;
  unavailable → UNKNOWN.
- Total denominator fixed at the four canonical source adapters.
  This is **not** a statistically independent or representative sample of
  leads, customers, geographies, trials or paid events.
- A source fingerprint digest is retained, but not a lead name, email,
  phone, address, tenant ID, API key or source payload.
- History is hash-linked and timestamps are monotonic, but has **no
  external anchor or cryptographic signer**. It detects accidental
  corruption; a privileged writer could still rewrite the journal.
- Exact repeated timestamps are idempotent. Conflicting repeats,
  malformed lines, missing newline after a simulated crash, tampered
  hashes, unknown source keys, unsafe symlinks, overlong and backdated
  observations fail closed. No silent history pruning.
- A genuine second observation must be separated by at least 24h; the
  interval has a maximum age of 30 days. Even then, distributions are
  descriptive only (four overlapping upstream data streams).
- A retained fingerprint is NOT provider source authentication, licence
  permission, buyer capacity, a settled transaction or model forecast
  calibration.
- `Evidently` is still an OPTIONAL import/extra, not installed in
  production. We should run it only with lawfully held real reference
  and current cohorts of sufficient quality, not synthetic
  pseudo-independent samples of four sources.

## Actual isolated baseline executed

On 19 October 2026, using a real read of the existing `/srv/empire_os`
source snapshots:

- Canonical source mining review: `MINING_REVIEW_READY`.
- Source adapter count = 4.
- Observed = 3, stale = 1, held = 0, missing = 0, unknown = 0.
- First observation sequence = 0, status
  `APPENDED_PRIVATE_SOURCE_QUALITY_OBSERVATION`.
- Private file with POSIX permissions `0600` in the ISOLATED feature
  worktree at
  `runtime/scientific_evaluation/flagship_source_quality_history.jsonl`.
- Readback validates a complete single-observation local hash chain.
- Comparison status =
  `NOT_POSSIBLE_WITH_ONE_SOURCE_SNAPSHOT`.
- This release performs NO Evidently statistical drift test,
  model training, tenant analytics export, CRM write, email, buyer
  activation, prediction registration or payment.

**Next internal quality action:** check the stale source in the existing
Source Intelligence review (the previously stale competitor feed).
Refreshing a stale feed is useful for research quality but does not prove
a new buyer or an increase in customer outcome.

The feature-worktree baseline is NOT an activated production service or
production data custody. Do not copy it into a live public portal without
the owning team reviewing the source provenance, release authority and
existing canonical writer rights.

## Files and manual operator commands

- `empire_os/flagship_source_quality_history.py`: strict read-only
  observation shape, SHA-256 journal validation, optional explicit
  local append and descriptive review.
- `scripts/review_flagship_source_quality_history_20261019.py`:
  default read-only preview; optional one bounded *worktree-only* capture.
- `empire_os/predictive_decision_control.py`: existing Founder decision
  includes `source_quality_history` read-only if a **canonical** journal
  later exists. No writer, schedule, network or DB migration.
- `apps/search-command-centre` existing Founder panel displays
  baseline/readiness, source category counts and next quality action
  after coordinated backend/UI release.
- `tests/test_flagship_source_quality_history.py`: exhaustive privacy,
  clock, replay, mutation, tamper, fake proof and local file durability.

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
# Reassess four existing sources without writing any file
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_flagship_source_quality_history_20261019

# On a genuinely new observation only, commit to the private feature journal
# ONLY after checking the same canonical source permissions and identity.
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_flagship_source_quality_history_20261019 \
  --capture-feature-baseline
```

## Next business-critical connection

Prioritise verification of one existing CRM buyer's buying brief,
product/service-area acceptance, price, allocation capacity and unit
economics. The canonical buyer Data Gateway was unavailable to the current
development actor in the previous read-only check. Restore access ONLY
through the existing authorised service identity; never create a
second unscoped reader or invent an exact-market count.

Then use verified original evidence to complete Quant Brain decision
packets, register pre-outcome forecasts, and measure actual settled and
fulfilled results in Economic Memory. This is the route from the flagship's
scientific credibility to demonstrable customer and enterprise value.
