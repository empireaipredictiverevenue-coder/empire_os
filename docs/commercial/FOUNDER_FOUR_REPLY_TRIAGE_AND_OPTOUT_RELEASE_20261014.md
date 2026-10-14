# Empire AI — Four canonical replies: triage and opt-out release

14 October 2026. Scope: review four already-ingested canonical reply threads, preserve no-send governance.

## Verified from live Founder API

- David at Gastley Law (29 September): direct 'Opt out' followed by quoted outbound copy. Do not contact.
- Jason at CCDocs (26 September): 'Please remove me from your mailing list.' Do not contact.
- Wolfgang at Tarrytown Roofing (23 September): reply exists, but body is '[provider body unavailable]'. Hold. No inferred interest.
- Dieter at Atlanta RC (20 September): subject 'opt out'; body unavailable. Do not contact.
- Previous view marked all four as unknown/unsuppressed because canonical snippets deliberately bypassed general sentiment classification; read-only viewer has no suppression-table visibility.

## Engineering staged; NOT YET applied to production

- empire_os/reply_opt_out_evidence.py: conservative leading-unquoted-text or exact-subject opt-out recognition. No positive-intent inference.
- empire_os/empire_mailbox.py: display protective no-contact holds for clear opt-outs even with preview-only bodies. Does not assert database suppression persistence.
- scripts/reconcile_three_founder_optouts_20261014.py: exact three reply IDs; root-gated, read-only review by default. Approved apply validates bound sender, intent, and content, then reuses canonical classify_outbound_reply with the empire_reply_ingest role, verifies suppression post-commit, and restarts only Founder API for display verification.
- The fourth reply is untouched. No email is sent; no automation or DNS changes.

## Approval boundary

Applying the suppression release writes three opt-out classifications, suppression records, related intent state and evidence events in canonical EmpireDB. It requires exact founder approval. The code is staged only.

Approved operator invocation (one time):

    cd /srv/empire_os
    sudo -n ./.venv/bin/python -m scripts.reconcile_three_founder_optouts_20261014 --apply --approved-three-explicit-optouts-only

Review-only option: --review. If an attempt returns HELD, do not retry until the cause is inspected.

Outbound remains OBSERVE and the original founder sending/receiving paths are unchanged.
