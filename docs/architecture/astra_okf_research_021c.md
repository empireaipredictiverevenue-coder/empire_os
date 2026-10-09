# Astra ↔ OKF Research Handoff — 021C

## Ownership and invariants
Keep `empire_os/astra_dispatcher.py` untouched while other agents are modifying
it. This 021C adapter only extends the existing Astra **department dispatch
report**, without changing executive plan generation, eligible steps, queue
enqueue semantics, review/suppression approvals, or worker execution.

The input is the already-present `empire.okf.private.v1` bundle, under
`runtime/knowledge/okf_private/run-*`. It is optional, explicitly opted in
with `scripts/dispatch_astra_departments.py --okf-bundle PATH`, and
validated through the same integrity/read-only layer SkillForge uses.

When an OKF bundle is supplied, Astra's report gains an
`okf_research_advisory` section containing at most 10 neutral research
references, company-domain concept IDs, observed relationship categories,
first-party source links, freshness flags and `trust: unverified`.

## Safety
- **OBSERVE**, research only; no model prompt, skill activation, task/job/queue
  creation, writeback, sender access or commercial-authority extension from
  an OKF document.
- Bundle must be located directly inside the canonical private runtime
  folder for the chosen repo root; external, linked or tampered inputs
  are `unavailable`, not accepted as policy.
- URL and relationship metadata are strictly validated; source excerpts and
  freeform OKF prose are **not** injected into any Astra execution prompt.
- Freshness is informational and is **never** proof of a real buyer, contact
  personhood, a completed sale, or permission to outreach.
- A missing bundle leaves the existing Astra report semantics unchanged,
  except for a null optional field.
- No new daemon, scheduler, cloud API, database or paid provider.

## Opt-in usage
Only in a specifically authorised internal Astra department report run:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/dispatch_astra_departments.py \
  --repo-root /srv/empire_os \
  --okf-bundle /srv/empire_os/runtime/knowledge/okf_private/run-<timestamp>
```

CAUTION: The pre-existing department dispatcher can enqueue legitimately
eligible internal work. Therefore use dedicated **isolated temporary repo
fixtures** to test the advisory integration; do not invoke the production
department dispatcher merely to preview OKF metadata.

A research-only direct preview is available through
`empire_os.okf_adapter.list_private_research` without touching queues.

## Acceptance criteria
- Bundle and manifest integrity checked, never using untrusted content as
  instructions.
- Tampered manifest, forged privileges/relationship, external path: fail closed.
- Approvals, work-queue transitions and skill trust pinned digests unaffected.
- Existing Astra dispatcher changes from other agents preserved.
- Integration production verification uses a synthetic empty Astra plan in a
  temporary repository, or directly uses the read-only OKF loader.
