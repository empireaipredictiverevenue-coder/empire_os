# Outbound Provider Event Ordering Architecture Delta V1

Date: 2026-10-02
Class: pure corrective maintenance / bounded DB delta
Owner: Governed Outbound provider-event ingest
Revenue purpose: prevent bounced recipients from remaining delivery-eligible after out-of-order provider lifecycle events

## Observed live defect

Resend accepted two governed sends after migration 030. For one recipient,
Resend emitted delivered followed by a Transient/General bounced event.
EmpireDB recorded both events but left the intent status as delivered.

Root cause: migration 024 only transitions delivered from sent or failed, and
bounced/failed to failed only from sent. That permits failed-to-delivered
resurrection and misses delivered-to-failed when a later bounce arrives.

## Correct state contract

- suppression remains terminal and unchanged;
- delivered may advance only sent to delivered;
- transient bounced / failed may advance sent or delivered to failed;
- permanent/hard bounce suppression remains owned by existing p_suppress;
- reply/suppression states are never downgraded by provider delivery events;
- duplicate provider events remain idempotent.

## Reconciliation

Migration 031 reconciles historical rows only where current intent status is
delivered and a recorded bounced or failed event occurred after the most
recent delivered event for that intent. No suppression is invented.

## Authority

No new role, grant, sender authority, cap, contact score, suppression rule or
revenue authority is introduced. Migration activation is founder-gated.
