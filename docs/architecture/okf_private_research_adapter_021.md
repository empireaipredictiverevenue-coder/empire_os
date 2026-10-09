# EmpireOS OKF v0.2 private research adapter — 021

This adapter exports selected **existing** Buyer Scout evidence as portable
Markdown + YAML concept files following Google's Open Knowledge Format v0.2.
EmpireDB, Buyer Scout, its evidence receipts and governed commercial controls
remain canonical. OKF is an export and retrieval format, not a new database
or a trust/approval mechanism.

The export is **private, create-only, OBSERVE**. Each concept carries
`type`, title, description, resource, tags, `generated`, `sources`,
`status: draft`, optional `stale_after` (30 days since source observation)
and explicit EmpireOS authority-denied extensions.

## Preservation and non-escalation
- Export only matching first-party company-domain source receipts, bounded to
  five source pages per company and up to 30 distinct candidate domains.
- Do not export candidate contact records, phone lists, person lists, email
  addresses or raw company-site bodies. Source snippets are shortened and
  email-like patterns redacted.
- Neither a positive legacy Scout flag nor a valid statement creates a
  `verified` OKF event. No human sign-off is fabricated.
- Source-text SHA-256 values are tracking metadata, **not** attestations of
  website authorship. The manifest SHA-256 catches accidental local changes;
  it is not independently signed and cannot authenticate a malicious
  replacement of both document and manifest.
- Bundle readers may use metadata for *research recommendations only*.
  Founder approval, verified person-email binding, sanctions/suppression,
  outbound, pricing, acceptance, wallet and payment gates are unchanged.
- Legacy Founder Objectives "OKF Tracker" is unrelated and untouched.

## How to run an explicit bounded pilot
From the EmpireOS repository root, with PYTHONPATH set to that root:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/export_buyer_okf.py \
  --scout-receipt runtime/buyer_acquisition/scout_latest.json \
  --output-root runtime/knowledge/okf_private \
  --max-records 30
```

Private bundle consists of `index.md`, `buyers/*.md` and
`manifest.json`. Export writes no EmpireDB tables and sends no outreach.
It does not fork Google's reference agent or require Gemini, BigQuery,
Google Workspace, a public repository or a paid provider.

## Operations and next phases
An initial manual observe-only acceptance uses up to 30 current Scout
candidates. If fewer real candidates exist, report the actual count instead
of filling with fabricated records. After the adapter is verified, consider
connecting read-only research browsing to SkillForge's existing trust registry
and Astra; do not create a new timer or modify another agent's files without
a scoped handoff. Automatic publication, retrieval promotion and human
verification are **not** enabled by this change.

Reference: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md


## SkillForge read-only integration (021B)
The `catalogue(okf_bundle_path=...)` optional argument and
`scripts/skillforge_catalogue.py --okf-bundle <private bundle>` expose an
advisory research list. Output contains concept IDs, source URLs, freshness,
unverified trust and explicit `execution_authority: none`. It does not load
source excerpts as instructions, create/publish skills, approve content,
or modify SkillForge's digest-pinned approval registry.

Invalid manifests, modified documents and any content claiming approved or
stable status are rejected into `okf_research.status: unavailable`. A valid
bundle does not affect `approved_count`, tenant policy or commercial execution.

Astra may consult the same read-only catalogue via a deliberate call; wiring
automatic Astra task dispatch or a recurring OKF export is **not** part of this
integration. No added timer or independent agent loop.
