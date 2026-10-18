# Empire AI Data Brokerage + founder-original provenance: revenue-first completion slice

**18 October 2026. Founder-approved goal: keep downloading free, legitimately reusable evidence, feed it to existing Empire AI intelligence and departments, and finish Data Brokerage without purchasing data services or starting a second platform.**

## What already exists; do not rebuild it

- **EmpireDB canonical Data Exchange, V15–V20**: protected UK Planning Data brownfield source custody, 3 pinned observed entities, immutable chain SHA, original-field/source-date lineage, bounded source fetch, official terms/attribution, privacy projection, read-only scientific quality inspection, eight evidence reviews. The real protected production inspection today returned **CANONICAL_CUSTODY_READONLY_VERIFIED, 1 observation, sequence 0**, latest observation 15 Oct 2026, **no field-change observation**, all commercial/resale flags OFF. A second capture is eligible by time but **has not been authorised/executed here**.
- Existing **Source Intelligence / department cycle** uses the live 7,765-observation NYC permit source, distinguishes official filing/issuance dates from import time and routes verified facts/unknowns to Market/Product.
- Existing **free Common Crawl 2026 domain graph review**: **1,974 historical relationships**, **1,870 historical referring domains**, **0 verified live backlinks**, 9GB+ raw file retained on disk, no bulk import and no paid API. The Marketing department has already received its first valid evidence receipt.

## What this slice added

### Product catalogue — four concrete brokerage offers (PRIVATE)

**One internal source-provenance-and-commercial inventory**; the delivery model for each is original intelligence/verification, not reselling raw downloaded data.

| Offering / target audience | Existing evidence | What we can genuinely prepare next | Limits |
| --- | --- | --- | --- |
| **UK brownfield site-change intelligence** — developers, renewable-energy developers, contractors, land research | Verified V15 canonical 3-source-record custody, source URL, official OGL v3 notice, original field/source date and recorded observation | Founder-review sample and verified dated site-monitoring briefs, original commentary and regional expansion on approved official feeds | 1 observation cannot demonstrate a source *change*. Field/third-party exception/privacy and notice verification needed for customer feed; no automatic data resale |
| **NYC permit-project verification** — builders, commercial roofing, HVAC/plumbing/electrical, B2B intelligence buyers | NYC official permit first-party observations; 62 recent imported but **historical** filings in 18 Oct cohort, 0 currently verified new project events | Buyer-relevant project briefs based on original filing/issuance and independent firm/subject evidence, plus expansion to current-source search | Old imports are not fresh construction. Owner/business/payer details require verification and privacy review |
| **Historical competitor domain graph intelligence** — SEO agencies, industrial/construction industry publishers | Approved free Common Crawl review: 1,974 historical relationships, 1,870 source domains | Original competitor research, candidate partnership/referral/SEO-source analysis with live verification before claims | Zero verified live backlinks; historical domain-level edges alone do not prove links, rankings or commercial rights |
| **Founder-owned original Empire AI reports** — agencies, roofing/solar/HVAC/dental, enterprise buyers | Founder declaration of his original work and first-party derived intelligence; existing $199/$249/$299 fixed-scope research deliverables plus £2,500/£7,500/£3,000/mo consultancy packages already present elsewhere | An original source-linked audit, opportunity assessment, competitor map or subscription proposal using Empire AI's analysis | Separate rights for downloaded source excerpts, images, fonts or other third-party material; founder ownership statement is not a universal third-party licence |

**The catalogue is an internal private evidence packet, NOT yet a buyer-facing marketplace, API, payment checkout, billable license or fulfilled order.** A clean offer is cheaper and quicker to sell than launching another platform before buyers actually respond.

### User-owned and AI-assisted provenance receipts

New `empire_os/founder_asset_provenance.py` implements:
1. Founder self-declared **ORIGINAL** or **FOUNDER-DIRECTED AI-ASSISTED** origin.
2. Exact SHA-256 hash/byte length of unmodified original file (regular allowlisted image/video/audio/document, no symlinks).
3. Parent-file SHA and human-readable transformation for a revision, preserving the origin/AI-assistance distinction.
4. Third-party components explicitly UNKNOWN, PRESENT or asserted absent (not independently proved).
5. Synthetic person/altered-real-scene disclosure checks using the existing Media OS policy.
6. Re-verification of file integrity later. No watermark stripping, metadata erasure, hidden authorship, fake signatures, false C2PA certificates or external model calls.

The server currently has no installed `c2patool` or `exiftool`. These are plain **local source-digest and ownership-declaration receipts**, not embedded C2PA credentials. They can establish a local evidence trail but **cannot guarantee AI-detector scores** or independently certify legal authorship.

The user has stated that the original inputs come from him. Treat this as a **founder declaration for identified first-party assets**; never assert that downloaded datasets or embedded third-party rights are therefore owned by him. Original Empire AI commentary can be creator-owned while the underlying government/data publisher retains its rights.

### Existing team integration / safe operator

Added internal `data_brokerage → strategy` Source Intelligence lane, triggered ONLY when a trusted 0600 private catalogue with correct source-evidence scope digest is available in the current canonical `runtime/data_brokerage/internal_product_catalog_latest.json`.

Production **read-only** operator reuses existing protected Data Exchange inspector via stdin (no DSN printed, no new DB roles/timer):
```bash
cd /srv/empire_os
set -o pipefail
sudo -n ./.venv/bin/python -B -m scripts.inspect_data_exchange_v16_live --read-only --rights-docket |
  ./.venv/bin/python -B -m scripts.preview_data_brokerage_products --read-only --inspection-stdin --materialize-private
```
Optional founder asset: pass `--founder-asset-file` with the local existing file path, `--founder-asset-id`, `--founder-origin FOUNDER_DIRECTED_AI_ASSISTED`, `--founder-ai-assistance AI_ASSISTED_DECLARED`, `--founder-ownership-declared`. The operator saves a private 0600 manifest to `runtime/media/provenance/<asset_id>.json`. It will not overwrite a changed original with the same ID; use another version ID. Source image is **never modified or moved**.

These receipts are reviewable by your existing team. The Source Intelligence worker never imports 9GB of crawl data, sends contacts to customers, invokes paid APIs, creates a fresh DB or grants data resale.

## Verified QA and actual privacy boundaries

- 112 focused and existing Data Exchange/rights/Founder Asset/Source Intelligence tests passed in the isolated worktree before promotion.
- Actual protected production **read-only** V16 custody was inspected; one canonical observation and rights held.
- First real read-only preview returned exactly four internal products, with `verified_payment_count=0`, `third_party_resale_authorized=false`, `customer_delivery_enabled=false`, `database_writes=false`.
- A historical Empire AI orbital review graphic in the existing website worktree can be hashed without changing it; founder claim is **SELF_DECLARED**, embedded fonts/third-party components still UNKNOWN and no C2PA certification claimed.
- Only a safe private product summary goes to `strategy`; owner names, phone numbers, raw source values and any paid API calls are not exported.

## Next steps without feature sprawl

1. **Commercial:** Have Sales/Strategy pick one of the four offers, deliver an *original* verified source-linked two-page sample, approach a real decision-maker with current suppression checks, seek a fixed-scope purchase. Do not invent a price for raw feeds; use existing approved intelligence report prices if appropriate.
2. **UK Data Exchange:** Finish a second **real** source observation only under the existing explicit capture authorization. Detect genuine source change with provenance, not simulated history.
3. **Evidence catalogue:** Expand source-specific rights/restrictions using actual official dataset terms and field scope. No mandatory paid lawyer or new blanket infrastructure. Do not assume source URL is a raw resale licence.
4. **Founder's content:** Apply SHA/version/AI-assistance/rights manifests to whichever exact logo, website hero, report, thumbnail or media asset the founder uses. Later add cryptographic C2PA issuance/verification using a trusted tool when available; don't claim a local hash equals a signed credential.
5. **Data cloud/Marketplace:** Once a real customer accepts terms, use existing CRM, Catalogue, direct checkout/payment evidence and Economic Memory. Customer data API or white-label resale remains a separate scoped capability.
6. **Other lanes stay active:** Permit, Property, Warehouse/Industrial, Storm, Private Capital, carrier DRP/contractor business research, legal/mass tort, SEO and YouTube all continue using the same evidence and downstream team contracts.

**Founder rule:** Revenue acquisition and safe product building both continue in parallel. Never solve content originality with watermark erasure, fake authorship, invented data sources or hiding genuine AI assistance.
