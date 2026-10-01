# Revenue Distribution evidence slice 2

Diagram: canonical source rows → explicit factor evidence validation → Radar
candidate partial inputs/refs → unchanged Revenue Distribution → locked formula.
AEO files → existing census → timestamped audit. Canonical company identities →
existing Search Fabric observer → competitor snapshot. Agent Web snapshot writer
was not found in repository/deploy/local service entrypoints; refresh is blocked.

Architecture delta: OBSERVE only. Worker: Codex. Verification: focused regression
suite, contract review, compilation, diff check, then bounded read-only refresh.
No database writes, execution, recognition, pricing assumptions or formula edits.

The three existing Radar source artifacts may carry explicit
`predictive_revenue_observations` on their source rows (research_queue,
pain_solution_briefs, or competitor payload). Each observation must contain
opportunity_key, factor, value, observed_at, evidence_refs, and
semantic_class=predictive_revenue_factor. Source and observation timestamps must
both be timezone-aware and at most 24 hours old. Association must resolve to
exactly one candidate and one source row. Conflicting/duplicate factor observations
are omitted. Unknown, proxy, stage scores, aggregate capacity and policy prices
are not formula evidence. No current inspected producer emits this explicit
contract; upstream factor production remains a blocker, not invented evidence.
The adapter is a guarded transport, not permission to attach arbitrary numbers.

Competitor public-only refresh restricts providers to unkeyed public engines,
rejects cached/error results, and preserves the old snapshot when there are no
fresh matched observations. Existing default provider selection is unchanged.

## Verification and refresh result

182 focused tests passed, including unchanged Revenue Distribution and formula suites.
Compilation and git diff --check passed. Formula and migration 018 unchanged.
Public gateway TestClient health test timed out; a standalone Starlette health
probe reproduced the same stall without Empire imports. Marketing tests pass with
AEO_SURFACE_ROOT set to a temporary test directory (default /srv/aeo is read-only).
AEO census genuinely rescanned 210 assets. Radar and Revenue Distribution rebuilt.
Competitor --refresh --public-only failed before search: dedicated
EMPIRE_INTELLIGENCE_MATERIALIZER_DSN absent; /etc/empire_os.env unreadable.
Agent Web snapshot writer absent from inspected code/service entrypoints; old
evidence preserved. No matching canonical factor producer currently emits the
explicit factor observation contract; bridge coverage remains zero.
Nothing activated, staged or committed. Existing dirty work preserved.

```json
{
  "source_timestamps": {
    "aeo": {
      "timestamp": "2026-09-28T23:46:37.410933+00:00",
      "status": "available"
    },
    "buyer_acquisition": {
      "timestamp": "2026-09-28T23:46:03.438533+00:00",
      "status": "available"
    },
    "buyer_capacity": {
      "timestamp": "2026-09-28T09:50:24.107589+00:00",
      "status": "available"
    },
    "buyer_scout": {
      "timestamp": "2026-09-28T10:53:17.115129+00:00",
      "status": "available"
    },
    "competitor": {
      "timestamp": "2026-09-22T14:04:38.210292+00:00",
      "status": "stale"
    },
    "crawler": {
      "timestamp": "2026-09-28T23:41:36.641857+00:00",
      "status": "producer_unavailable"
    },
    "exchange": {
      "timestamp": "2026-09-28T23:46:03.174448+00:00",
      "status": "available"
    },
    "radar": {
      "timestamp": "2026-09-28T23:46:37.550251+00:00",
      "status": "available"
    },
    "search": {
      "timestamp": "2026-09-17T14:56:56.412084+00:00",
      "status": "stale"
    }
  },
  "radar_opportunities": 21,
  "with_factors": 0,
  "factor_coverage": {
    "demand": 0,
    "quality": 0,
    "enrichment": 0,
    "omega_qualification": 0,
    "buyer_match": 0,
    "outreach": 0,
    "conversion": 0,
    "terms": 0,
    "payment": 0,
    "fulfilment": 0,
    "ltv_cents": 0
  },
  "complete_evidence": 0,
  "calculable_revenue": 0,
  "proposals": 26,
  "blockers": [
    "acquisition_budget_unknown:zero_cash_planning",
    "competitor:stale",
    "crawler:producer_unavailable",
    "search:stale"
  ],
  "distribution_timestamp": "2026-09-28T23:46:37.741672+00:00"
}
```
