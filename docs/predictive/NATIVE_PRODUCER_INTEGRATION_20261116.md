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

## Founder-approved activation follow-through, 16 November

The founder explicitly instructed execution of the outstanding deployment and
credential/writer configuration. Fresh original-reader authentication at
17:25 UTC confirmed registry rows 0 and all seven completed dates 9–15 November
with zero qualifying tenant events, each `DAY_CENSUS_INCOMPLETE_HOLD`. This is
now a live seven-day source observation, not inference from the old receipt.
The native registrar had zero role members; no existing restricted predictive
writer candidate was present for the original tenant.

The bounded additional activation prepares one dedicated forecast login using
the original NOINHERIT/SCRAM/tenant-binding pattern. It receives only membership
of the existing native registrar, CONNECT, a four-second statement timeout, and
one active original tenant binding carrying the founder approval reference.
No schema migration, tenant creation, generic app privilege or reader-write
grant is included. Existing loopback SCRAM authentication avoids any HBA change.
`prepare_native_writer_login` was verified on disposable PostgreSQL before live
use; only a derived SCRAM verifier enters its SQL, never a plaintext password.

`deploy/systemd/empire-department-cycle-predictive-native.conf` delivers the
original reader and separate writer through systemd's private read-only
per-service credential mount. The original root reader vault stays unchanged;
no credential is stored in application source or Environment values. The
observer validates the credential mount/path/file protections and uses the
original source identity, without a reader-to-writer fallback. It refreshes
source preflight through the original restricted readers in memory on each
existing scheduled invocation, rather than treating a stale root receipt as a
fresh database query.

The existing hook, timer, promotion gate and other department steps are
preserved. A live department-cycle `exit-code` failure was traced to
`promote_predictive_revenue_runtime_bindings.py`, which correctly refuses held
source evidence; this is not proof that the observer did not execute, and no
speculative hook relocation or scheduler redesign is applied.

Focused regressions after the activation adapter: **76 passed**. Added checks
cover unmanaged credential refusal, sanitized missing-credential holds and
creation/duplicate denial of the dedicated writer with exactly one capability.

Activation installed six reviewed source files, created the separately scoped
writer with original tenant binding, verified its real SCRAM authentication and
function-only capability in a READ ONLY session, and installed the credential
configuration via daemon-reload. Neither PostgreSQL nor the department service
was restarted. Independent catalogue readback verifies single SET-only writer
membership, no reader/writer crossover, no direct commercial/registry DML,
no generic-app writer membership, no schema CREATE privilege, safe registrar
attributes and FORCE RLS. Both original and new persistent credential vaults
remain root-owned 0700/0600.

Actual service-namespace verification found systemd 259 delivers credentials as
root:root 0440 plus an exact named service-user read ACL inside its private
read-only mount. The 0440 group mode represents the ACL mask, not group access.
The adapter now verifies the exact five-entry ACL: root read, service UID read,
no group access, read mask and no other access. It also accepts protected
service-group 0440 or service-owned 0400 layouts, while rejecting additional
users/groups, writable or world-readable variants. This does not
weaken original vault custody. The added regression brings the focused total
to **77 passed**.

Final registration-clock hardening checks the expected issuance UTC date against
the returned DB timestamp **inside** the registrar transaction. A midnight
rollover therefore rolls back before commit rather than leaving an immutable
forecast for a target day inconsistent with its model origin. Actual original
REV078 SQL in the isolated fixture verified that refusal leaves zero rows.
Final focused suite: **79 passed**, with one existing Starlette deprecation
warning. The exact service-user ACL was positively verified in the real
systemd service namespace using the service UID and a read-only invocation;
original readers authenticated and correctly held on empty source history.

## Live scheduled acceptance — 17:52:23 UTC

The original normal department-cycle invocation (not a manually written
receipt) generated `predictive_revenue_runtime_latest.json` at
**2026-11-16T17:52:23.432660+00:00** with:

- `native_reader_credential_delivery=SYSTEMD_SERVICE_SCOPED`;
- `source_preflight_origin=LIVE_ORIGINAL_RESTRICTED_READERS`;
- original registry reader authenticated, scoped registered rows **0**;
- producer `AUTHENTICATED_SOURCE_DAY_EMPTY_OR_INCOMPLETE`;
- source reader called, one authenticated source day read before stopping on
  the earliest empty input day; independent earlier live reads verified all
  seven completed dates 9–15 November have zero qualifying events;
- model not called, registration not attempted, no forecast write;
- outcome readiness `NO_MATURE_NATIVE_FORECASTS`, calibration unauthorized.

The existing timer and hook placement were unchanged; no service restart,
HBA change, schema migration, synthetic production data, financial recognition
or outbound occurred. The department cycle still exits at its original
promotion gate because held/empty forecast evidence is not promotable; the
observer executed successfully before that gate. This restriction was not
suppressed or bypassed.

Technical activation is complete. No additional deployment approval is pending
for this approved delta. Genuine first-party qualifying history and later
independently final financial outcomes remain business/evidence dependencies;
they cannot be manufactured by connecting the database. Actual production
forecast registration/readback is not claimed at N=0. The real native insert
and independent exact restricted readback are verified only in the isolated
PostgreSQL integration tests until legitimate source inputs exist.
# Founder-authorized NewsJack deployment — 16 November, 18:15 UTC

The founder explicitly requested production deployment after the source-only
handoff. Commit `36edc619d` on this existing PR branch reuses the exact original
NewsJack/JEV source files from owner commit `511bbf20b` and connects the real
MediaOS Last30Days handoff to the existing department-cycle observer.

Deployed only `empire_os/jev_newsjack_traffic.py`,
`empire_os/jev_newsjack_adapters.py`, `scripts/review_jev_newsjack_traffic.py`,
and `scripts/run_predictive_revenue_runtime_observer.py`. Existing source and
systemd drop-in were checked for concurrent drift before atomic replacement.
The existing drop-in gained three non-secret NewsJack research settings:
enabled=1, sector=ai, market=GB. This is explicit operator research scope,
not proof of publisher geography, customer demand or buyer qualification.

Source and config bytes independently matched the committed review. Only
`systemctl daemon-reload` was used; no service restart, new unit, migration,
role change, paid provider, outbound message or publishing action.

The existing observer writes research status, exact source hash/time,
per-topic citations and intake/review/hold counts into its original receipt.
The connector is fail-closed and separately reports source/adapter problems
without breaking native financial source inspection. Research references are
never passed into the recognized-revenue model or registered as money.

36 focused observer/native integration tests passed; the original NewsJack
adapter's 46 tests had already passed on its owner branch. A read-only run of
the deployed code processed the current MediaOS handoff generated at
`2026-11-16T18:11:58.615326+00:00`, SHA256
`b4f37ae219b4e9c9710ec6bb223eccc197e12dca57c7d3b8a24d9f4bd38995bf`:
12 references across three topics; six `RESEARCH_REVIEW`, six held by the
unchanged seven-day news gate. No malformed entries or within-topic duplicates.
Independent original tenant registry authentication at 18:15:50 UTC still
reported zero forecasts. These research observations do not satisfy the
original commercial-history/model/financial-outcome requirements.

**Normal scheduled production acceptance:** the existing department-cycle
observer wrote its original runtime receipt at
`2026-11-16T18:22:06.124639+00:00` with
`newsjack_research.status=ORIGINAL_LAST30DAYS_NEWSJACK_RESEARCH_REVIEWED`.
The source hash, three topic counts and six-review/six-hold breakdown matched
the deployed read-only check above. Credentials remained
`SYSTEMD_SERVICE_SCOPED`; native producer status remained
`AUTHENTICATED_SOURCE_DAY_EMPTY_OR_INCOMPLETE`; registry status remained
`AUTHENTICATED_REGISTRY_EMPTY_NO_FORECASTS`; database write=false.
This receipt was generated by the original scheduled hook, not a manually
written acceptance record. No new scheduler or worktree import path is used.
# Predictive Cloud product readiness and bounded API hardening — 18:38 UTC

Founder requested completion to enterprise quality. Current product inspection
used existing source owners and GET-only live routes; no fabricated customer
case, production enquiry, financial row, payment or report finding was created.

Verified live: Founder API health, Cloud status and product workbench return
HTTP 200. Original enterprise JSON/HTML/Markdown routes each pass their
existing evidence guard with no-store/nosniff headers. These are explicitly
internal drafts, with zero verified customer findings and customer delivery
disabled. An HTTP 200 does not establish product fulfilment. Cloud status
reports 29 components available; stale/unknown source freshness prevents its
overall framework-operational flag. That is a freshness classification, not
proof every engine or API has failed. No flag was forced green.

The current status API accepts wrong-schema objects as available, reads
unbounded files and lacks private-cache headers. Prepared source correction
in `empire_os/predictive_cloud_status_api.py`:

- Bounded regular-file descriptor read, no symlinks/FIFOs, no nonfinite JSON
  numbers, required original schema/mode/authority/components contract.
- Current v2 snapshots require an aware, nonfuture generation clock within
  30 minutes. Legacy v1 compatibility explicitly reports unknown age.
- Invalid sources return unavailable metadata and preserve conservative
  revenue/customer/operational flags; do not expose exception/source content.
- Existing status route gains Cache-Control:no-store and nosniff.
- No API path, service, customer data store, forecast model or permissions added.

28 focused API/observer tests passed. Read-only review of the actual production
v2 snapshot passed the new reader and retained commercial prediction=false,
customer forecast=false and framework operational=false. Root/source bytes
were checked against the existing owner branch before edits; no shared dirty
report/workbench/status-builder files were overwritten.

Activation is not complete: `empire-founder-dashboard-api.service` reports
CanReload=no. Its standing process started 13 November 22:40:13 UTC. Direct
Founder router modules have not been modified since that start (metadata
check), but deployment still requires the founder-controlled one-service
restart retained by the user's earlier execution controls. The correction is
staged on the established PR branch, not represented as running HTTP code.

Other pending product work remains distinct: original report/workbench/demo
and status-builder paths contain other owner changes in production. Preserve
their ownership and reconcile through the existing owner before modifying
them. A customer-released diagnostic and empirical revenue/accuracy claims
require real customer source evidence; this pre-sales business has no sales
history. Newscitations/research cannot supply that evidence.
