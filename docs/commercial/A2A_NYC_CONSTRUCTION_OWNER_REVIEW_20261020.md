# NYC construction data intelligence: commercial source preflight

Date: 20 October 2026. Owner: A2A Commercial Signal Miner (research only).
Branch: feature/a2a-commercial-signal-mining-20261020

## Real evidence from existing EmpireOS runtime

The current three-agency NYC permit research file contains 36 source-linked event rows.
Its SHA-256 matches the separately stored founder-directed derived receipt:
c9c343cc7821dd81c2b0e2767a1593ac76de28aa0f5ba0e66cc4d2ab6b75957c

Join evidence counts: TRI_AGENCY_BIN_AND_LOT_MATCH 25; DCP_LOT_ONLY_BIN_UNCONFIRMED 10; BUILDING_TAX_LOT_CONFLICT 1. These are permit event classifications, not verified unique buildings or customer identities. Tax-lot land-use classifications cannot prove operating business use.

Current NYC general-contractor market research priority is 80/100. This is an internal research ordering score, not probability of a purchase. The market snapshot reports zero approved buyers, zero commercial demand evidence and zero commercial terms. Neither the report digest nor the score independently authenticates a commercial buyer.

## Official general source-policy guidance

NYC's official Open Data FAQ says there are no general restrictions on the use of NYC Open Data:
https://www.nyc.gov/opendata/get-started/FAQs

NYC's technical manual describes the public data programme and the originating agencies' continued data stewardship:
https://www.nyc.gov/assets/doitt/downloads/pdf/nyc_open_data_tsm.pdf

Dataset pages for the four component inputs:
- DOB NOW approved permits rbx6-tga4: https://data.cityofnewyork.us/d/rbx6-tga4
- DOB NOW job application filings w9ak-ipjd: https://data.cityofnewyork.us/d/w9ak-ipjd
- DCP PLUTO 64uk-42ks: https://data.cityofnewyork.us/d/64uk-42ks
- OTI building footprint 5zhs-2jue: https://data.cityofnewyork.us/d/5zhs-2jue

The generally permissive guidance is encouraging; this does not replace verification of dataset-specific terms, source attribution, privacy and every included field in the commercial product. Public permit records may contain personal, private or sensitive fields. Rights and relevance must be reviewed by Data Brokerage before customer delivery.

## New implementation

The research branch contains:
- empire_os/a2a_nyc_commercial_evidence_gate.py
- empire_os/a2a_data_campaign_release_review.py
- scripts/review_nyc_a2a_pilot_preflight_20261020.py

The script reads existing snapshot files without sending network requests or modifying them. The --review-campaigns --write-local flags save the preflight and campaign-release verdict in this worktree under runtime/a2a_commercial_signal_mining.

The NYC source digest and event totals pass the research-integrity checks. Commercial gates remain held: product-specific distribution rights not attested by the owner, no approved NYC buyers in the market snapshot, and no verified NYC purchase terms. All five targeting campaign drafts remain research-only. No posting, outreach, payments, CRM writes or campaigns launched.

## Required existing-owner handoffs

Data Brokerage: review per-dataset reuse/attribution, privacy, field selection and original value-added report content; issue a signed product-specific release record only when justified. Do not infer clearance from a sample report.

Buyer Scout: independently validate NYC commercial construction firms' relevance, actual decision-making roles and willingness to purchase project intelligence. Reuse canonical records and avoid duplicate research or contact. The A2A miner has no prospect promotion or outreach authority.

Commercial Terms: obtain a real accepted field specification, permitted use, target market, pricing and settlement schedule from the actual buyer.

Owned Campaigns / ASTRA: produce a rights-backed value proposition and one focused original first-party opt-in content test after founder approval for exact account, targeting, consent and creative. No personal social data harvesting.

Finance OS: prepare provider-hosted checkout or canonical governed settlement only if a legitimate buyer agreement is in place; do not expose account credentials to an agent.

A2A Identity: review the local capability card for signed identity and trusted registry integration. A local card does not create a publicly authenticated agent.

## Reproduce read-only research

From the dedicated worktree run:

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.review_nyc_a2a_pilot_preflight_20261020 --review-campaigns --write-local

Outputs are nyc_commercial_preflight.json and data_campaign_release_review.json in the local runtime folder. Execution authority is NONE. Decision: HOLD commercial launch, continue legitimate B2B research.
