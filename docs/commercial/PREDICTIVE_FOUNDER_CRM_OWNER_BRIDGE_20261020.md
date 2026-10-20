# Predictive Commercial — Existing Founder CRM Reader Integration

20 October 2026 — safe feature scope, on-demand OBSERVE only.

## What is genuinely integrated

The new `empire-predictive-observe commercial-crm` invokes the existing
Ubuntu-scoped `scripts.probe_founder_sales_visibility_readonly` in
`/srv/empire_os`. It does **not** create a customer form, database role,
new intake collector, A2A agent, API route, CRM writer or timer.

The adapter executes an exact allowlisted module through `subprocess.run`
(no shell, privilege elevation, inherited application credentials or arbitrary
input). It checks that the existing source module is a regular non-symlink file,
uses a bounded timeout and output, suppresses untrusted diagnostic streams,
and strictly validates the owner schema, read-only flags, total-count
consistency and "canonical source receipts not checked" claim. It emits only
three permitted aggregate counts and status/hold codes.

Existing query path: dedicated, least-privileged founder CRM sales reader,
tenant-scoped native EmpireDB view. It can report zero/nonzero tenant-visible
prospects. Neither implies a genuine new buyer; counts never prove exact
original website acquisition, customer purchasing authority, consent, signed
terms or payment.

## How to check now

```bash
~/.local/bin/empire-predictive-observe commercial-crm
```

Expected schema:
`empire.predictive_revenue.existing_founder_sales_crm_bridge.v1`.
This returns a structured HOLD rather than fake zeros if the existing reader
is unavailable, malformed or changes contract. No source data or secret appears
in the output.

## Remaining original provenance link — owned by canonical source team

The production scripts already exist:

- `scripts.probe_canonical_sales_intake_aggregate_readonly`:
  original canonical acquisition aggregate; **privileged local operator only**.
- `scripts.probe_founder_sales_visibility_readonly`:
  existing least-privilege founder CRM tenant-visible aggregate.
- `scripts.reconcile_founder_sales_handoff_aggregate_readonly`:
  original two-source reconciliation, including contradiction checks and a
  single evidence-review next action.

Do not reimplement their database queries or grant new DB privileges. The
original reconciler must be run as a separately approved privileged local
read-only operation by its existing owner. This integration intentionally
cannot call it by elevation. It would be false to treat a zero CRM count as
proof of zero first-party canonical acquisitions.

For an owner-authorised local read-only review:

```bash
cd /srv/empire_os
sudo -n /srv/empire_os/.venv/bin/python -B \
  -m scripts.reconcile_founder_sales_handoff_aggregate_readonly --review-only
```

Review the resulting aggregate status. If one genuine source acquisition and
corresponding tenant projection exist, original *per-record* lineage and exact
customer authority must still be independently authenticated by the existing
CRM/source owners. An aggregate count or a pasted JSON snapshot alone is not
that proof.

## Safety boundaries

No production merge, service restart, CRM insert, permission change,
outbound message, lead reservation, paid activity, funds movement or training.
No assumption of lead supply from source inventory counts. The six founder
intake planning values remain unfilled until a real founder/customer instruction
supplies them. The commercial-custody evidence gates remain held.

Validation: `tests/test_predictive_existing_founder_crm_bridge.py` plus the
pre-existing commercial/Predictive regression suite. The existing pinned
release builder checks the new source files in its critical checksums and
smoke-tests the one-hit reader without needing canonical privileged access.
