# Company-Routed Duplicate Guard Architecture V1

## Goal

Prevent a company or prospect that already has outbound send history from
re-entering the founder-gated company-routed review queue.

## Flow

deferred buyer evidence
-> first-party company route
-> named economic buyer
-> canonical outbound-history/suppression read
-> duplicate guard
-> founder-review queue

## Rules

- Canonical EmpireDB outbound history is checked before queue materialization.
- A prospect with prior send-attempt/sent/delivered/replied/suppressed history is excluded.
- A company domain with that history is excluded even if a new generic mailbox appears.
- A suppressed route email is excluded.
- History lookup runs in a read-only database transaction.
- If canonical history cannot be read, the materializer fails closed and does
  not publish a fresh review queue.
- No send authority is added. Company-routed outreach remains founder-gated.
