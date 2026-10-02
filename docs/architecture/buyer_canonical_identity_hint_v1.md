# Buyer Canonical Identity Hint V1

## Goal
Reduce broad identity recovery when Empire already has a named decision-maker hint on the canonical prospect.

## Contract
The canonical prospect fields `contact_name`, `contact_title`, and `contact_source` may be reused only as a targeting hint.

A hint is eligible only when:
- the name passes the existing person-name guard;
- the title maps to an existing decision role with score >= 0.50;
- the existing queue item does not already contain explicit target people.

The hint does not become verified evidence by reuse alone.
It must pass the existing targeted buyer probe and person-bound contact gates.
No outreach authority, commercial authority, payment authority, or revenue recognition is added.

## Flow
canonical prospect identity hint -> targeted first-party probe -> existing evidence gates -> review proposal or durable defer

## Safety
No synthetic identity or email.
No authority expansion.
No new queue.
No database migration.
No outbound send.
