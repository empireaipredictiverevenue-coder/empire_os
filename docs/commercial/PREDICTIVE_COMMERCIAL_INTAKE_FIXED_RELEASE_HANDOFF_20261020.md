# EmpireOS — Commercial Intake Error Recovery and Next-Agent Handoff

**20 October 2026 | Owning code:** Existing Predictive Intelligence / Predictive Cloud feature worktree
`/home/ubuntu/empire_agents/predictive_decision_control_20261018`

## Task completed

A founder generated `/home/ubuntu/commercial_requirement.json` with the deployed `commercial-template` launcher and then ran `commercial-intake`. It failed with:

```text
ValueError: explicit supported country region and city required
```

The actual original JSON file exists, has **23 expected source contract keys**, and at the inspection checkpoint had **zero substantive fields filled**. The original file must **not** be overwritten, guessed from an example, or silently treated as an authorised customer order.

**Root cause:** `commercial-template` intentionally creates `null` essential fields; the strict downstream `review_commercial_requirement` requires country, state/region, city, industry, currency and positive target. The first release failed to separate **draft readiness** from **full owner-planning validation**.

## Fix implemented

New `empire_os/predictive_commercial_intake_readiness.py` inspects only the known field names/shape and reports:

- `COMMERCIAL_INTAKE_MISSING_PLANNING_FIELDS` with exactly the field names needed to start a research *draft*, and a hint for each;
- `COMMERCIAL_INTAKE_INVALID_STRUCTURE` when the JSON includes unknown/missing schema keys (no private values echoed);
- `COMMERCIAL_INTAKE_PLANNING_FIELDS_SUPPLIED` when the minimal typed scope has been supplied, **still not independently validated or customer authorised**.

Updated `scripts/review_predictive_commercial_requirements_20261020.py` converts absent required fields into a **successful readable incomplete result** on stdout; neither a traceback nor an implicit Tampa market. It refuses to fetch Finance/A2A/Lead Supply owner data or prepare tickets when the requirement is incomplete. Invalid JSON/unsupported values/forged receipts fail closed with readable JSON status and nonzero exit code; no private values leaked.

Updated `scripts/prepare_predictive_readonly_release_20261020.sh`: integrity manifest includes the new inspector, original intake operator, and template. Atomic staging now tests both the blank-template round-trip and the rejection of nonexistent `/path/to/request.json`. No production service, database, agent, buyer, campaign or source-owner worktree is modified.

## Supported operator procedure

```bash
# An existing editable file is already present at the founder's path.
# Inspect and edit it, do NOT overwrite its contents by regenerating a template:
nano /home/ubuntu/commercial_requirement.json

# Save in nano: Ctrl+O, Enter; exit with Ctrl+X
~/.local/bin/empire-predictive-observe commercial-intake /home/ubuntu/commercial_requirement.json
```

Minimum planning fields to fill from a **real user/founder/customer instruction** (no defaults, example values are not customer facts):

| JSON key | Format | Scope |
|---|---|---|
| `country` | supported ISO country, e.g. `US`, `GB`, `CA` | No default geography |
| `state` | region code, e.g. `AZ`, `LON` | No assumed territory |
| `city` | literal target city | Source state/region checked |
| `industry` | `roofing`, `hvac`, `solar`, `construction`, `insurance`, `agency`, `data_brokerage`, `professional_services`, `software`, `other` | Exact original niche taxonomy |
| `currency` | matching original country currency; e.g. `USD`, `GBP` | No implied FX |
| `requested_qualified_leads` | positive integer (e.g. `20` only when actually requested) | Target **not** lead inventory |

Other fields (valid billable lead type, company/tenant scope, permissions, accepted channels, ZIPs, due date, price, exclusivity, capacity, refund terms, physical material needs) should be filled **only when supplied or independently approved**. Nulls stay null, owner-authentication receipts must not be forged by editing the JSON. With only the six fields, the engine may conduct an OBSERVE-only **research draft**, but its commercial entitlement, actual inventory, customer signed terms, buyer purchase and cash-profit status remain unverified.

## Deployment scope

Latest deployment consists of an immutable, commit-pinned **read-only release** under `/home/ubuntu/empire_releases/` and a verified shortcut at `/home/ubuntu/.local/bin/empire-predictive-observe`. The prior pinned read-only release and rollback launcher remain available. It does not install a web/API service, worker, systemd timer, multi-agent message bus, CRM writer, subscription, advertising campaign, or purchase flow.

**Do not confuse publishing the source and launcher with live departmental integration.** The actual A2A, Lead Supply and Finance owners still need canonical original event, permissions and independently authenticated outcome receipts before live commercial activation.

## Validation and handoff

Run:
```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_predictive_commercial_intake_readiness.py \
  tests/test_predictive_commercial_intake_template.py \
  tests/test_predictive_commercial_requirements_operator.py
```

Then `bash -n scripts/prepare_predictive_readonly_release_20261020.sh`, verify checksums and review profiles. Confirm no tracebacks from the actual blank file and that its contents are unchanged.

**Next agent priority after this completed UX fix:** get approved real intake source, authenticated buyer role and exact niche/territory terms, the existing Lead Supply owner's actual consent/ZIP/dedupe readback, and A2A original authenticated owner pickup; subsequently Finance/Quant confirmed original forecasts and realised gross profit, followed by Predictive Cloud constrained allocation. Avoid unnecessary new agents or second source collectors. Treat unavailable proof as unknown; do not infer target availability, payables or gross profit.
