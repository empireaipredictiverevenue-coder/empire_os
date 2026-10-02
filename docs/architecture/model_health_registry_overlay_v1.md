# Model Health Registry Overlay v1 — Architecture Contract

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Intelligence Router / Model Upgrade Layer

## Problem
`runtime/llm/receipts.jsonl` contains live provider outcomes, and
`empire_os.model_health` reduces them to a persistent health state. The installed
model registry currently ignores that state, so a route with repeated production
failures can continue winning on static quality priors.

Observed production evidence on 2026-10-02:
- `gemini/gemini-3.1-pro-preview`: 50 samples, 0 successes, 50 failures;
- health state: `degraded`;
- router still selected the same model because registry health remained `unknown`.

## Contract
Model Registry overlays live health after configured/discovered model loading.

Health key: `<provider>:<model>`.

Rules:
- `degraded` with >=5 samples -> `available=false`, `health=degraded`;
- `healthy` -> remain available, `health=healthy`;
- `warning` -> remain available, `health=warning`;
- unknown/missing health -> preserve configured availability;
- health never changes configured quality priors;
- health never invents pricing/cost;
- health overlay metadata records sample/success/failure/latency evidence;
- registry config remains canonical policy; runtime health is eligibility evidence.

## Promotion / demotion boundary
This slice implements **automatic operational demotion/recovery** only.
It does not promote a model's quality rank from health alone. Quality promotion
still requires matched-pair workload calibration.

## Verification
- degraded model excluded from candidates;
- warning/healthy model remains eligible;
- missing health preserves configured state;
- live router no longer chooses the 50/50 failing Gemini 3.1 Pro route;
- no provider call required to perform the demotion;
- no authority expansion.
