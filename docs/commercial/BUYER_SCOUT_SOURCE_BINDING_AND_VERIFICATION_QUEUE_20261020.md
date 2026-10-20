# Buyer Scout — individually verified first-party evidence and stable owner queue

20 October 2026 | Read-only owner update

## Existing services and source scope

Existing worktree:
  /home/ubuntu/empire_worktrees/resilient_buyer_scout_business_release_996946a3

Existing downstream hourly user timer:
  empire-buyer-scout-a2a-owner-evidence-review.timer

The prior intake had a recency label for a whole cached source batch but
could not match every owner handoff to its *particular* first-party collector
readback. A spoofed label, source hash or mismatched sector could appear
as research-review-ready without crosschecking the independent site readback.

This release closes that gap and produces a deterministic owner verification
queue from existing A2A evidence. It does not operate a new search or browser
agent.

## Modules

- empire_os/buyer_scout_first_party_evidence_binding_20261020.py
  - Ensures exactly one original readback row per handoff packet.
  - Compares exact approved HTTPS company site, target market/sector, fetch
    status and original HTML SHA256.
  - Requires Scrapling and Crawl4AI extraction digest checks for HTTP200
    sites before labelling source binding independently evidenced.
  - A robots-policy or oversized-page hold cannot have an HTML digest,
    be treated as verified fetch, or be retried with an alternate crawler.
  - Rejects any reviewer metadata claiming a buyer or allowed contact.
- empire_os/buyer_scout_a2a_research_intake_20261020.py
  - Per-site source proof is now a mandatory criterion for active identity
    research review. Whole-batch freshness alone is insufficient.
  - Returns number of individually source-bound, within-window websites.
- empire_os/buyer_scout_source_verification_queue_20261020.py
  - One stable SHA-derived task ID per source identity. Recomputing hourly
    does not generate new duplicate IDs.
  - Founder-priority order: Tampa roofing, Little Rock HVAC, NYC general
    contractors; this is a work-planning order, NOT a demand score.
  - Keeps policy/source holds separate from real approved HTTP200 evidence.
  - Keeps older official permit company names as HISTORICAL CONTEXT, not
    an active HVAC purchase or homeowner-lead claim.
  - Explicit work required: independently corroborate company and license,
    territory, actual demand to buy leads, budget, canonical EmpireDB
    duplicates, suppression, and authorized rights BEFORE any outreach.
- scripts/review_buyer_scout_a2a_source_intake_20261020.py
  - Existing scheduled owner review automatically writes a second,
    isolated, atomic, 0600 local output:
    runtime/buyer_acquisition/a2a_source_verification_queue_latest.json
  - Keeps original intake report unchanged in file name:
    runtime/buyer_acquisition/a2a_research_owner_intake_latest.json
  - Both files contain only independently captured company-site source
    receipts and separately licensed official public permit context,
    NO raw Brave Search results.
- tests/test_buyer_scout_a2a_source_binding_queue_20261020.py
  - Checks site SHA, market, parser digest, duplicates, source hold,
    missing batch rows, buyer claim tampering, stable task IDs,
    permit stale flag and zero contact authority.
  - Existing source-intake unit tests updated to reject unbound recency
    claims rather than credit a freshness label alone.

## Real observed owner-side output

As of 20 Oct 2026, reviewed previous A2A source receipts:
  - 9 company website status packets supplied.
  - 7 website receipts individually bound and eligible for independent
    research review (3 Tampa, 3 Little Rock, 1 NYC).
  - 2 non-readable/held NYC sites, NOT retried.
  - 7 older official permit company-name hypotheses separated.
  - 0 actual buyers verified, 0 canonical database queries conducted,
    0 messages sent, 0 owner tasks dispatched externally.

The existing working production job
  empire-buyer-acquisition-scout.service
still has UnsetEnvironment=BRAVE_API_KEY, intentionally preventing its
historical scheduled search sweep from consuming Brave credits or storing
Brave search results.

This update does NOT merge into dirty /srv/empire_os, does not approve
CRM activation, produce buyer contacts or run paid searches.

## Next ownership gates

1. Sales/Buyer Scout: independently verify real lead purchasing demand,
   company and service territory, actual buyer capacity and budget,
   suppression, prior conversations, and owner-issued authentic receipts.
2. Canonical EmpireDB owner: use approved read-only authoritative CRM
   checks to reconcile duplicate company matches. Current source
   comparison covers only snapshots and is not database-wide.
3. Source owner: obtain Brave Search API storage rights if using its
   search results as persisted research inventory; otherwise keep
   Brave search diagnostics transient-only.
4. Release owner: review and merge the isolated feature branch and unit
   tests into an appropriate clean mainline release.

## Smoke-test

cd /home/ubuntu/empire_worktrees/resilient_buyer_scout_business_release_996946a3

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m \
  scripts.review_buyer_scout_a2a_source_intake_20261020 \
  --read-only-owner-review --write-local

cat runtime/buyer_acquisition/a2a_source_verification_queue_latest.json

XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  systemctl --user start empire-buyer-scout-a2a-owner-evidence-review.service
