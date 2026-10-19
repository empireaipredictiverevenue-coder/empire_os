# Empire AI Predictive Intelligence — First-party market knowledge graph and saved-example learning

19 October 2026 | Owner branch feature/predictive-decision-control-20261018

## Product objective

Prepare ASTRA and Empire's scientific/commercial reasoning from broad,
lawful market information BEFORE a genuine buyer conversation starts.
Combine markets, products, observable problems, permitted research,
industry reports/analytics, buyer questions, objections, and approved
hypothetical dialogue. The future buyer interaction should be informed,
relevant and specific, NOT an invented forecast or an unrequested sales
message.

**One knowledge graph; not one new datastore per feature.** We reuse the
canonical EmpireDB authority model and existing CORTEX, Buyer Demand
Graph, Source Intelligence, Community Intent, Quant Brain and Economic
Memory. This wave is a pure source-joined GRAPH PROJECTION in Python,
not a new PostgreSQL migration or external Neo4j/graph server. The
eventual canonical graph persistence should be added to EmpireDB under
separate schema/tenant/ownership review, and stored examples may require
a separate approved source vault.

## Wave 1 implemented graph topology

Nodes include:

- Registered public research sources (14 from existing ICP source atlas),
  with source access and automation modes, explicit reference-only reuse.
- Market verticals/geographical scopes, product/offer hypotheses.
- Existing eight intelligence data products, each with an evidence hold.
- Known market problem topics from existing SOLUTION_MAP.
- Deidentified **hash-only** public observation references when an
  original cached post has a valid HTTPS Reddit subreddit identifier
  that matches the catalogued source AND observed niche.
- Research analytics report (existing Community Intent retrieval cycles,
  not economic impact) and its known source-diagnostic edges.
- Optional permissioned **scenario lessons**, with explicit
  human review, source content digest, and retrievable curated lesson
  key; no original chat text in the graph.

Edges are strictly source-typed:
RESEARCH_SOURCE_COVERS_VERTICAL,
RESEARCH_SOURCE_DECLARES_SCOPE,
SOURCE_RESEARCHES_OFFER,
MAY_INFORM_OFFER_HYPOTHESIS,
MAY_INFORM_DATA_PRODUCT,
CITED_FROM_PUBLIC_SOURCE,
UNVERIFIED_TOPIC_TAG,
REPORTS_ON_RETRIEVAL_HEALTH,
EXAMPLE_TEACHES_MARKET,
EXAMPLE_ILLUSTRATES_THEME.

A public conversation can be tagged with a general problem theme;
no inference attaches its author to a canonical buyer, CRM tenant,
buybox, pricing, demand contract, capacity or revenue. Research signals
and model examples do not create BUYER_DEMANDS_LANE edges; those remain
in the existing stricter Buyer Demand Graph.

### Scientific/copyright/privacy controls

- Raw text, title, author, contact details and original post URLs are
  NOT emitted in the market graph, Founder Console or CLI.
- Research source linkage requires exact known source/subreddit/niche
  identity, not fuzzy vector similarity to a different company.
- Public content is INDEXED REFERENCE ONLY; no assumed right to reproduce
  forum data, resell a dataset or train model weights. Licensing,
  data-protection and ToS review is still required for any future
  text retention or corpus training.
- Learning is initially *knowledge retrieval and source selection*,
  NOT stochastic model weight changes. The Scientific Agent must
  separately evaluate answer quality with prospective held-out examples.
- Only signed/canonical commercial receipts may later establish real
  buyer conversations, buying budgets, agreed terms, fulfilment or revenue.
- Missing, out-of-window or unrecognised source data is held, not
  silently mapped to the nearest vertical.
- Reports do not establish causal market share or conversion
  probabilities. A stale competitor feed is not promoted to live truth.
- No network requests, model inference, data scrape, buyer contact,
  payment, CRM write, outbound, service activation or database migration.

## Observed real first checkpoint

On 19 October 2026, an explicit read of existing `/srv/empire_os`
community snapshots (NO remote collection) produced:

- 14 declared research-source venues.
- 8 existing intelligence data products.
- 12 cached public forum observations; **4** could be safely joined
  to known exact subreddit/niche sources. **8** were quarantined due
  to untrusted/unmapped source or other strict source filters.
- Community learning source diagnostics: **11** mapped source IDs,
  **3** separately unmapped source IDs. All 14 appear in the
  research log. Do not invent source attribution for the three extras.
- Graph: **50 nodes, 72 typed edges**.
- Agency discussion preparation: 2 approved source venues, 3
  attributable discussions; source-tag counts lead_generation=3,
  automation_ops=1, sales_conversion=1 and search_visibility=1.
  Counts are correlated topic tags, NOT four separate buyers or sales.
- Historical saved ChatGPT examples approved/ingested in this wave:
  **ZERO**. An approved import contract and tests exist, but no
  complete past-conversation archive was exposed to the runtime and
  no permission ledger exists yet. We must not invent or import private
  chat messages by inference from the founder's memory.

## How the founder's saved conversation examples will be onboarded

The founder has asked for ALL useful previous examples to inform the
brain. Treat this as a **curation and evaluation programme**, NOT a
blanket scrape of every user/customer/assistant conversation.

1. Export or otherwise obtain the founder-controlled *relevant* example
   archives through an authorized read-only channel. The current model
   conversation context is NOT a complete reusable transcript corpus.
2. Extract explicit scenario type and intended learning objective:
   lead qualification, industry-specific objection, pricing,
   delivery capacity, data-provenance challenge, no-contact preference,
   technical support, upsell/retention, legitimate refusal,
   contradictory evidence or verified customer-success correction.
3. Classify each as SYNTHETIC_SCENARIO,
   PERMISSIONED_DEIDENTIFIED_EXAMPLE, genuine CRM/tenant source
   (must remain outside the founder-global graph), or REJECTED.
4. Remove contact details, private buyer/company data, names,
   credentials, tenant secrets, commercially sensitive figures,
   confidential support cases, unverifiable results and prompts that
   assert authority the user never granted.
5. Obtain explicit reuse permissions, human approval, source/content
   checksum, decision owner and revocation path. Different customers
   do not implicitly consent to cross-tenant learning from their chats.
6. Map approved examples to a bounded fixed **lesson key** and market
   vertical. Only lessons and origin hashes enter this graph. The
   original raw chat is **never stored in this projection**.
7. Test retrieval and conversation quality on held-out synthetic
   scenarios against a no-context baseline. Do not train model weights
   or call paid providers by default. Correctness, objection handling,
   source citations, uncertainty and risk must improve before promotion.
8. Add independent deletion/revocation and a future signed approval
   journal before persistent EmpireDB graph or tenant-facing reuse.

### Approved lesson contract

File location (feature-worktree private ONLY):
`runtime/knowledge_graph/approved_examples.json`.

Optional command imports this private file only with `0600` permissions,
one hard link and exact manifest schema. This is a **manual test import**,
not a production approval signer. Every row must have:

```json
{
  "example_ref":"example_roofing_001",
  "lesson_key":"VERIFY_SERVICE_AREA",
  "niche":"roofing",
  "approval_class":"SYNTHETIC_SCENARIO",
  "human_approved":true,
  "reuse_permission":"INTERNAL_RETRIEVAL_ONLY",
  "contains_personal_data":false,
  "original_commercial_outcome_verified":false,
  "text_retained":false,
  "evidence_content_sha256":"<64 lower-case hex digest>"
}
```

Only seven currently reviewed lesson classes may be attached:
ASK_FOR_ORIGINAL_BUYING_BRIEF, VERIFY_SERVICE_AREA,
VERIFY_UNIT_PRICE_AND_MARGIN, VERIFY_DELIVERY_CAPACITY,
EXPLAIN_UNKNOWN_VS_ZERO, COMPARE_ALTERNATIVE_CHANNELS,
ASK_FOR_FULFILMENT_ACCEPTANCE.

The manifest wrapper is `schema_version=`
`empire.knowledge_graph.curated_scenarios.v1`,
`human_reviewed=true`, and `examples=[...]` bounded to 80.
The SHA digest shown above is a placeholder, NOT an operational file
with a valid example and NOT evidence that any user consent was received.
Malformed/unapproved rows HOLD; arbitrary raw transcript fields are
rejected. The CLI emits only safe counts and curated lesson keys.

## Code entrypoints

- `empire_os/flagship_market_knowledge_graph.py`:
  typed bounded graph builder, privacy-preserving source joins,
  example admission, known-source analytics report edges,
  read-only niche-specific market conversation preparation.
- `scripts/review_flagship_market_knowledge_20261019.py`:
  explicit read-only live-snapshot review, optional separate
  private curated-example test manifest.
- `empire_os/predictive_decision_control.py`:
  attaches a SAFE SUMMARY and six market-prep briefs to the existing
  Founder-only decision contract. Does not expose full graph payload.
- `apps/search-command-centre/src/app/founder/page.tsx`:
  source/market graph status and first review theme for roofing, solar,
  HVAC, agencies, B2B and law. Not deployed.
- `tests/test_flagship_market_knowledge_graph.py`:
  source URL/license constraints, privacy, duplicate posts,
  stale references, source diagnostic unmapped IDs,
  strict customer-chat admission, role of synthetic lessons,
  deterministic graphs and no invented commercial proof.

Read existing source snapshots without writing:
```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_flagship_market_knowledge_20261019 --market agency
```

Only after founder curates a local manifest in the isolated worktree,
it can be explicitly tested with:
`--include-approved-private-scenarios`.

## Next knowledge-source expansion (not claimed connected)

The desired full flagship graph should eventually include:
- Permits, weather/storm, tender/procurement, business registrations,
  corporate actions and regional capacity (original public rights
  checked and exact entity matching).
- Search Analytics/GSC, SEO/AEO/GEO demand shifts, industry reports,
  UK/US market forecasts, Common Crawl *lawful references*, first-party
  source observations, authority and competitor change history.
- Insurance, legal, mass tort, medical/dental, construction, finance,
  technology, SaaS, local services, private capital and more market
  ontologies—**no construction-only limitation**.
- Scientific paper/reproducibility records and contradictory reports;
  preserve opposing views, publication date and uncertainty instead of
  overwriting the less convenient observation.
- Tenant-scoped verified buying briefs and consent receipts via the
  existing CRM private authority, NEVER founder-global leakage.
- Original prospective predictions from Quant Brain, verified
  outcomes from Economic Memory and calibrated model changes
  by prospective evaluation.
- Explicit tenant-aware graph traversal, retention, rectification,
  revocation, right to deletion, temporal versioning and original
  source/data-product entitlements.
- The existing CORTEX/ASTRA retrieval tool should read a narrowly
  shaped brief, not raw poisoned web text or the entire graph, until
  its evaluation and tool authority are verified.

**Production activation gate:** graph projection and Founder UI source
are committed only to the owner feature branch. No production source
changes, worker activation, EmpireDB schema or customer application
deployment in this wave.
