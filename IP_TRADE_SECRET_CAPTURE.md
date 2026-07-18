# EMPIRE LEAD-ENGINE — IP & TRADE-SECRET CAPTURE

Document owner: Empire AI (empire-ai.co.uk)
Date: 2026-07-16
Classification: INTERNAL / TRADE SECRET — do not distribute
Reference ID: 585a5f3f-1fbc-4f0d-869c-2d3e981341e1
Scope: lead-generation engine, payment rail, data-integrity pipeline.

---

## 0. PURPOSE
This document establishes the novel, protectable elements of the Empire lead
engine so they can be: (a) held as TRADE SECRETS now, (b) copyrighted as code,
(c) evaluated for patent eligibility later once revenue validates the method.
It deliberately contains NO API keys, credentials, or infra addresses.

---

## 1. TRADE SECRETS (protect by secrecy + access control)

### TS-1 — Multi-Source Free-Tier Search Orchestration
A method that fuses several independent free-tier search APIs (Serper.dev,
SerpAPI, Parallel.ai, Serply.io, Serpstack, Brave) into a single deduplicated
domain stream. Novelty: each source is queried in rotation; results are merged
by normalized domain; failed/rate-limited sources are skipped without breaking
the pipeline. This achieves "Apify-scale" SERP coverage at $0 recurring cost
by exploiting the aggregate of free tiers instead of paying for one paid tier.
Code: search_api_leads.py (serper_domains / serpapi_domains / parallel_search /
serply_search / serpstack_search + merge logic in hunt()).

### TS-2 — No-Simulation Lead Provenance Pipeline
A data-integrity method guaranteeing every stored lead is a real, reachable
business: each prospect is keyed by sha1(domain); emails are extracted only from
live business contact pages or from inline SERP excerpts; phantom/simulated rows
are purged by design (never inserted). Source is attributed per lead
(source='serper:logistics' etc.) for traceability + audit. This is a defensible
differentiator vs. polluted list vendors.
Code: search_api_leads.py register(); empire_lead_crawler.py overpass_domains().

### TS-3 — Inline-Email Extraction from SERP Excerpts
A scraping-avoidance technique: contact emails are mined directly from search
result snippet/excerpt text (e.g. Parallel.ai returns "first@domain.com" in the
excerpt), eliminating the need to fetch + parse the target site for those leads.
Reduces per-lead latency + footprint.
Code: parallel_search() excerpt mining loop.

### TS-4 — Overpass OSM as a Bot-Wall-Free Lead Source
Using OpenStreetMap Overpass API (structured business data, no CAPTCHA/bot wall)
as a primary domain source when search APIs rate-limit. Fuses open geo-data with
search-API enrichment. Rotates multiple Overpass public mirrors + multi-region
bbox to avoid per-IP rate limits.
Code: empire_lead_crawler.py overpass_domains() (4 endpoints × 8 US regions).

### TS-5 — Crypto-Native B2B Lead Settlement (Solana USDC)
A payment rail where lead buyers deposit/settle in USDC on Solana mainnet — no
Stripe, no KYC, no traditional merchant account. Lead royalties flow programmatically.
Payment processor is the vault; settlement is on-chain. Novel for B2B lead
marketplaces which are traditionally card/KYC gated.
Code: empire_os/solana_listener_agent.py; vault logic.

### TS-6 — Lane / Seat-Corridor Monetization Model
Business method: lead inventory is organized as "lanes" (verticals/corridors);
buyers occupy "seats" and pay per-lead at a seat_price tier (bronze/silver/gold/
platinum/titanium). Revenue model is decentralized — buyers are tenants, not
subscribers. Detail lives in g-brain/revenue/pricing.md (kept separate, secret).

---

## 2. COPYRIGHT (code artifacts — auto-protected on creation)

File                                      Lines  Protectable element
----------------------------------------  -----  ------------------------------
/root/empire_os/search_api_leads.py        226   TS-1, TS-2, TS-3 orchestration
/root/empire_os/empire_lead_crawler.py     244   TS-4 Overpass fusion + loop
/root/empire_os/captcha_farm.py            131   Multi-browser CAPTCHA harness
/root/g-brain/revenue/pricing.md            —     TS-6 tier model
/root/empire_os/empire_os/solana_listener_agent.py — TS-5 settlement

Action: keep these under version control (private repo). Add LICENSE + copyright
header. Do NOT publish keys/config in commits.

---

## 3. PATENT ELIGIBILITY — CANDIDATES (evaluate with counsel post-revenue)

P-1: "System and method for aggregating free-tier search APIs into a unified
      deduplicated lead domain stream" (covers TS-1).
P-2: "Method for verifying lead authenticity via source-attributed domain
      hashing and live-contact extraction" (covers TS-2/TS-3).
P-3: "Decentralized lead-marketplace settlement using stablecoin payment rails
      without KYC" (covers TS-5).

Note: business-method patents (TS-6) are jurisdiction-sensitive; prefer
trade-secret protection until a defensible claim is drafted.

---

## 4. SECRECY CONTROLS (required to maintain trade-secret status)

- API keys live ONLY in /root/empire_os/.env (host) + container copy.
  Never commit. Rotate if exposed.
- This document stays INTERNAL. Do not paste into public chats/forums.
- Access to TS-1..TS-6 code limited to authorized agents.
- If open-sourcing, strip TS-1/TS-4 orchestration specifics; publish only the
  generic interface.

---

## 5. NEXT ACTIONS

[ ] Add copyright headers to the 4 code files.
[ ] Move pricing.md + this doc into a private, access-controlled repo.
[ ] Schedule patent counsel review after first paying tenant lands (validates P-1/P-2).
[ ] Register "Empire AI" + "Empire Leads" trademarks (brand moat).
[ ] Keep keys out of git (verify with git-secrets / pre-commit scan).

---
END OF DOCUMENT — TRADE SECRET
