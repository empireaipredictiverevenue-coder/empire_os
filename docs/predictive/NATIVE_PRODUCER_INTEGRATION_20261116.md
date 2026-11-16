# Original native forecast producer integration — PR #165

16 November 2026. Owner: existing Predictive Revenue implementation branch
`agent/predictive-forecast-evidence-separation-20261115`. This change is staged
source engineering, not a deployed or authenticated customer forecast.

## What was broken and what changed

The original `predictive_materializer.materialize_daily_actuals` invokes
`predictive_cloud_v3.forecast_observed_metric`, but neither it nor a scheduled
production caller invoked `EmpireDbProspectiveForecastRegistration`. The
public preview accepts request-supplied points; it must not become a trusted
native producer. REV076–078 installation alone cannot generate observations.

The original department-cycle hook already invokes
`scripts/run_predictive_revenue_runtime_observer.py`. Its optional private
branch now calls the original materializer, authenticates original REV077
completed-day census observations, invokes REV078 through the restricted
transport, and opens an independent READ ONLY registry connection for exact
reference/model/value/evidence/target/time readback. It uses the existing
observer output; no new service, scheduler, agent or registry is introduced.
The default remains OBSERVE with no DB writes. `run(write=False)` cannot
register even when the registration flag is configured.

Seven contiguous completed UTC source days are required. Each day must be an
authenticated positive REV077 candidate; unknown/empty days are not zeros and
stop before the model. The model uses issuance-day horizon semantics to match
REV078, rather than incorrectly treating yesterday as today's forecast origin.
The existing API retains its default preview semantics. Native output rounds
to exact integer cents and preserves bounded model identity and a deterministic
source/model-code digest. Fit confidence is not calibrated forecast accuracy.

REV077's candidate inputs do **not** independently certify upstream ledger
completeness, financial finality or customer permission. Registered output is
therefore a provisional first-party source forecast, not a finance-certified
customer forecast. All original REV078 unverified-source/finality/calibration
flags remain unchanged. No maturity/finality boolean supplied by a caller can
promote this record. When native targets mature, the same workflow reads their
original registry records and target-day REV077 census. The original scorecard
is deliberately not executed on financially unverified candidate labels.
Original finance custody/finality remains a real dependency, not replaced by
new invented attestations or tests.

Repeated runs read the deterministic tenant/model/version/target/horizon key
before writing. Exact existing records are verified without another insert;
changed inputs produce an immutable conflict HOLD. A lost commit acknowledgement
or duplicate race triggers only independent readback, never an overwrite or a
second key. Uncertain commit state remains explicit. No raw observations,
customer amounts, credentials or tenant IDs enter the observer receipt.

## Live evidence and limits

The founder-deployed native schema and original tenant login are the production
baseline. The original source preflight generated at 16:24:39 UTC reports:

- registry reader authenticated, scoped observed rows **0**;
- census reader authenticated, completed source date **2026-11-15**, events **0**;
- census status `DAY_CENSUS_INCOMPLETE_HOLD`;
- verified forecast/outcome pairs **0**, calibration held.

At 16:39 UTC the updated observer was executed against this existing production
receipt with `write=False`: `AUTHENTICATED_REGISTRY_EMPTY_NO_FORECASTS`, scoped
rows 0. Its private source probe correctly returned
`NATIVE_SOURCE_CONFIGURATION_HOLD` without source/model/registration calls;
this unprivileged execution session has no dedicated source/reader/writer
credentials. This was a receipt read, **not** a fresh database authentication.
No original root-vault credential was extracted or copied.

The existing department cycle and autonomous revenue service are running.
Their process state does not prove seven accepted source days, revenue events
or financially final outcomes. There is no evidence to label the broader
customer-ingestion estate empty or broken from one empty completed day. The
prior missing registrar caller is verified by source inspection. This PR's
private path is not installed in production; live scheduling and activation
remain owner/founder-controlled. No live forecast was inserted by this work.

## Exact minimal activation delta — founder/DBA gate, not performed

Deploy the reviewed commit through the existing owner release path, preserving
all effective systemd overrides. Do not run the legacy Incus deploy script,
reapply REV076–078, change the existing schedule or grant any writer capability
to the evidence login.

The existing scheduled observer needs these **service-managed** settings:

- `EMPIRE_PREDICTIVE_NATIVE_SOURCE_ENABLED=1`
- `EMPIRE_PREDICTIVE_TENANT_ID`: original canonical tenant
- `EMPIRE_PREDICTIVE_CENSUS_DSN`: original restricted source reader
- `EMPIRE_PREDICTIVE_REGISTRY_READER_DSN`: original restricted registry reader

Initially keep `EMPIRE_PREDICTIVE_NATIVE_REGISTRATION_ENABLED` unset. This
runs source/model/readback checks only and reports a writer HOLD when eligible
inputs exist. Do not place credentials in a shell command, PR or report.
Existing root-owned reader custody must remain root-owned. If the scheduled
identity cannot consume an approved scoped reader, the existing owner must
resolve credential delivery; do not chmod/copy the root evidence vault.

A writer requires an **already existing, approved, tenant-bound, restricted
login**, separate from both evidence and registry readers. This change neither
creates nor assumes such a production login exists. If none exists, its
identity/custody requires founder/DBA selection through the existing mechanism.
The helper `predictive_registry_transport.prepare_native_writer_grant` prepares
the exact minimal transaction for DBA review. It validates the original active
single-tenant binding and a NOINHERIT/non-superuser/non-bypass/non-admin login,
refuses reader-role members and generic app/migrator identities, then grants
only:

```sql
GRANT empire_predictive_forecast_registrar TO <approved_existing_writer>
 WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
```

No direct table INSERT/UPDATE/DELETE, new role, tenant mapping, login, password
rotation or reader grant is included. This transaction was executed only in the
disposable PostgreSQL fixture, including denial for the original reader.
Rollback of this new capability is the narrowly scoped DBA `REVOKE
empire_predictive_forecast_registrar FROM <approved_existing_writer>`; do not
revoke original reader memberships or delete forecasts.

Only after founder/DBA approval, configure `EMPIRE_PREDICTIVE_REGISTRAR_DSN` for
that writer and `EMPIRE_PREDICTIVE_NATIVE_REGISTRATION_ENABLED=1` in the existing
service's protected configuration. This work has not made that configuration
change or performed any restart/deployment. The transport independently refuses
an evidence/registry-reader login even if it is mistakenly granted the writer
role. Original DB session-user tenant resolution and FORCE RLS stay mandatory.

First live success requires `NATIVE_FORECAST_REGISTERED_AND_READ_BACK` with exact
separate-reader comparison. A HOLD is not success; no synthetic forecast may be
inserted to obtain the status. If a valid source day is absent, the commercial
source owner supplies genuine observations through the original event pipeline.
A later financially final outcome requires the original finance owner's
independent completeness/settlement/refund evidence before scoring/calibration.

## Verification

Focused pytest includes a disposable PostgreSQL 18 cluster, Unix socket only,
with original REV076/077/078 SQL and the actual Python source reader, model,
registrar and exact restricted readback. Every fixture observation/order/event
and forecast is **synthetic and isolated**, never customer evidence. Checks
cover repeats, changed-source conflicts, cross-tenant denial, invalid/missing
days, refused elevated reader, lost commit acknowledgement, guarded writer grant,
original scheduled entry-point invocation, read-only mode and mature outcome
census without financial promotion. Original reader/authentication and
materializer regression tests are included. Production SQL files are unchanged.

Final focused verification: **73 passed** (including 13 native integration checks); one existing Starlette/AnyIO deprecation warning. Python syntax/compilation and `git diff --check` passed. This is isolated engineering evidence, not customer activity.
