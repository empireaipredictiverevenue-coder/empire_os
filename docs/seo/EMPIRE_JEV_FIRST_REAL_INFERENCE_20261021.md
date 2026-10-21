# Empire AI — TypeSafe Jev actual inference: first bounded SEO pilot

Date: 21 October 2026. Mode: manual **one-shot shadow**. Status: actual model result verified.

## Why this is now real
The existing EmpireOS typed-decision contract and SEO task board were only planning interfaces, without Jev model invocation. The owner explicitly asked to enable real inference. A working, existing OpenRouter credential was found in the Ubuntu-only \`/etc/empire_os/llm_secrets/openrouter.env\` (0600). This release does **not** copy or expose it.

The model was called exactly **once** through OpenRouter's separate TypeSafe Decisions API:
- Endpoint: \`https://openrouter.ai/api/alpha/decisions\`
- Pinned model: \`typesafe/jev-1.13\` (actual response \`typesafe/jev-1.13-20260917\`)
- Request: one source aggregate plus three typed questions (Choice, Score, Noul)
- Source: existing first-party GSC page-dimension **sample from 2026-10-07 through 2026-10-19**, 32 returned page rows, 30 legacy missing-page rows, 44 associated impressions, 15 core editorial-review candidates.
- No raw page URL, search query, contact details, customer data, credentials, private buyer information, live emails, or advertising spend was sent.
- Jev returned \`ABSTAIN\`, decision confidence \`0.46\`, probabilities \`ABSTAIN=0.57\`, \`SOURCE_AUDIT=0.33\`, human-review yes probability \`0.84\`, and investigation-priority score \`0.76\` on the 0–3 four-level scale.
- Reported usage: **707 input tokens**, **$0.000029694**. One inference call. This is **not accuracy verification**, conversion proof, commercial ROI or permission for a redirect.
- The real receipt is stored outside Git at \`/home/ubuntu/empire_releases/search_jev_owner_receipts_20261021/seo_jev_one_shot_receipt_v1.json\` (0600, parent 0700).

## Operational integration
- New \`jev_live_pilot.py\`: manual, bounded, server-side REST client with pinned HTTPS destination/model; one request; max 1400 bytes of scalar state; <=3000 billed input tokens, <=$0.0005 accepted reported cost; validates all three typed outputs; no redirect, retries, autofallback, outbound, publishing or payment authority.
- New \`scripts/run_search_jev_one_shot_20261021.py\`: safe dry-run by default. A live call requires \`--live-one-shot --owner-approved-no-publication\`. An existing receipt prevents repeated billing.
- New \`jev_pilot_receipt.py\`: read-only contract validation of an actual external provider receipt; strips all extra fields; never calls the provider. Existing loopback Search Intelligence API exposes \`GET /v1/search/jev/pilot/receipt\`.
- Existing Quora Founder workbench source adds an actual-pilot evidence panel distinguishing 1 real result from 0 real labelled Quora cases. This new frontend must be independently rebuilt as an immutable Research-compatible release before touching the current Founder service.

## Still blocked
- **Unattended inference OFF**: no timer, event trigger, automated retrier or unlimited API usage.
- **Accuracy promotion blocked**: no real reviewed intent/SEO outcome labels, provider calibration, drift benchmark or independent QA; the observed model answer is a candidate only.
- No SEO/Quora posting, paid traffic/editorial, GSC indexing claim, live call routing, database write, money movement or permission elevation.

## Owner-controlled replay check
From the canonical worktree:
\`\`\`bash
cd /srv/empire_os
PYTHONPATH=. .venv/bin/python -B -m scripts.run_search_jev_one_shot_20261021
PYTHONPATH=. .venv/bin/python -B -m scripts.run_search_jev_one_shot_20261021 --live-one-shot --owner-approved-no-publication
\`\`\`
The second command intentionally returns \`pilot_already_completed_no_repeat_billing\`; it does **not** charge again.
