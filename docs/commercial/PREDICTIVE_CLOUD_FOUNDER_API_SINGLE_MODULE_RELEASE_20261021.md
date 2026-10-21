# Predictive Cloud — existing Founder API single-module integration

**21 October 2026**. Existing owners: this Predictive Cloud branch and the deployed EmpireOS Founder read-only API. This is an additive, fail-closed module replacement, not a new dashboard, endpoint service or rewrite of CRM/mailbox routes.

## Live situation

- Guarded Cloud materializer **`5caaa4106769`** is installed, healthy, with the original two-minute timer active; trend, formula and local optimisation inventory refresh under root-owned `/opt/empire/predictive_cloud_guard_5caaa4106769`.
- Current Cloud status contains 28 available artifacts, 25 fresh, `founder_directives` genuinely stale, and `commercial_loop` and `astra` missing independently reliable freshness timestamps. Neither customer forecasts nor live economic outcomes are verified.
- The **Founder** API service `empire-founder-dashboard-api.service` uses an original historical-bridge overlay `/home/ubuntu/empire_worktrees/empire_founder_api_hist052_bridge_additive_20261018` (24 router entries). Its `empire_os/predictive_cloud_status_api.py` still implements the legacy permissive JSON reader, which exposes the new Cloud fields but does not independently validate source freshness and forecast governance.
- Existing owner's `empire_os/predictive_cloud_status.py` declares exactly the same 28 components as the pinned new source, so the only required API change is the status reader module. It does not require replacing the original Founder service or associated modules.

## Completed compatibility and safety verification

The updated status API module was imported **from the immutable Cloud release** into a simulated existing Founder app with the original overlay and dependency path. Its FastAPI health route and Predictive Cloud status endpoint passed. No running service source or runtime was touched.

The guarded installer `scripts/install_guarded_founder_cloud_status_api_20261021.sh`:

1. Checks exact Cloud commit SHA `5caaa410676942890caba41924d95338680466f1`, root-owned immutable source SHA, original API source SHA and active Founder service.
2. Checks the source of the original 24-router Founder service, its prior Cloud status component definitions, its base systemd unit and the four existing distinct service drop-ins by exact SHA; refuses drift or a second active release.
3. Keeps the other routes, login, mailbox, commercial overlays and Cloud timer untouched; atomically replaces **only** `predictive_cloud_status_api.py` in the current read-only Founder overlay, after copying its original to a privileged backup.
4. Restarts only `empire-founder-dashboard-api.service`; validates local `/health` and the actual loopback `/v1/predictive-cloud/status` response. Requires v2, exactly 28 components, zero execution/payment/outbound authority and no verified customer forecasts.
5. On any failed validation, restores the exact prior source module and restarts the existing Founder service. No database, payments, outbound, data migration, Cloud timer or model training changes.

**Remaining scientific boundaries** are real customer outcomes, independent issuer/tenant authentication, original frozen pre-outcome forecasts, and proper cohort calibration. No form submissions, buyer contacts, fake training outcomes or automatic source timestamp refresh were performed.

## Operator command after preflight

```bash
sudo -n bash \
  /home/ubuntu/empire_agents/predictive_decision_control_20261018/scripts/install_guarded_founder_cloud_status_api_20261021.sh \
  --apply-owner-approved-observe \
  5caaa410676942890caba41924d95338680466f1
```

Requires one explicit root-controlled restart of the **existing** Founder API; the agent's remote executor cannot carry out the privileged service restart. Do not mistake the local shadow verification for this live deployment.
