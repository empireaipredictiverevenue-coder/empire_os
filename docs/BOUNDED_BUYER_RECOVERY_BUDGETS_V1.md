# Bounded Buyer Recovery Budgets V1

The high-volume buyer enrichment cycle remains 48 candidates across up to 8
parallel lanes.

Cheap first-party/site probes stay broadly parallel. Expensive recovery stages
are bounded independently per lane:

- identity recovery: maximum 1 attempt per lane;
- exact-person public contact recovery: maximum 1 attempted search per lane.

This prevents slow public search or identity recovery from holding GTM behind
the 300-second service wall. Unresolved buyers remain durable and re-enter on a
later cycle under the existing retry/backoff policy.

No personhood, contact-verification, suppression, review, outbound, payment, or
revenue authority is weakened.
