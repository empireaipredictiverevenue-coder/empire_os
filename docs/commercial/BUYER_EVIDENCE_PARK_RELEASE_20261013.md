# Buyer evidence-based retry park — 13 October 2026

**Status:** Isolated source/test change; NOT merged, deployed or runtime loaded.

## Production truth observed (read-only)
- Existing production buyer-enrichment timer is active; no additional timer/agent is justified.
- At inspection, the source queue held 2,136 durable records; 16 were resolved, and the observed unresolved population was 2,120.
- All 131 high-priority unresolved buyer records had already reached at least eight retries; 17 were in the named-person contact-recovery lane and 114 were quarantined by existing prioritisation. Zero high-priority rows were due at the readback.
- The live supervisor still had zero genuine review-ready buyers, with no payment, outbound or call-routing activation authority.
- A real hot recovery record carried 1,140 attempts. Previous 'quarantine' only sorted such rows last; it did not remove them from the automatic retry cycle.

## Minimal bounded source fix
- For records without new source evidence, park weaker recovery lanes after eight attempts and hot named-person contact recovery after 32 attempts.
- Never claim, retry or count an exhausted row as due solely because its backoff expires.
- Keep original records, reasons, retry history, consent/outbound authority and review gates unchanged.
- Reactivate only on a *distinct* existing-contract first-party same-host named-person evidence URL or verified contact route. Re-ingestion of identical or unrelated evidence does not reset the budget.
- If such evidence arrives while a worker owns an unexpired lease, keep that lease, preserve the delayed wake, and reset attempts when the worker defers so the new source gets a bounded chance.
- Add `evidence_parked_count` to the queue snapshot without concealing unresolved backlog. Production supervisor remains CRITICAL until genuine review-ready buyer evidence exists.

## Independent proof / limitations
- First focused tests: 40 passed.
- Broader scoped suite: 69 passed after aligning one pre-existing mock to the current worker's `target_people` keyword call. The mock change is test-only.
- Running the *isolated branch's read-only* queue snapshot against the unchanged production JSON projected: 2,136 total; 2,051 parked pending/deferred records, zero currently due. The queue's SHA-256 matched before and after the inspection.
- Those are **candidate-policy projections**, not a deployed production result. No live worker restart, DB mutation, external send, traffic, payment or call occurred.
- The first buyer closing path still requires independently verified company and decision-maker/contact binding, compliant suppression, exact product/terms, founder authority and verifiable settled revenue.

## Operational handoff
Review the bounded branch `feature/buyer-evidence-park-20261013`, test with a representative local copy of the production queue if required, then obtain an explicit deployment/restart scope before touching the existing worker. Do not rerun the parked 2,051 records blindly. Focus fresh source collection on the 17 hot and 114 high-priority quarantined prospects; a new first-party evidence item may reawaken the correct existing row. Never infer a sale or create a new outreach automation from these counts.
