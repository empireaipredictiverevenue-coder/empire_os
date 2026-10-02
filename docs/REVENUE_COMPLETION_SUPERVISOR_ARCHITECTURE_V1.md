# Revenue Completion Supervisor — Architecture Contract V1

Autonomous Revenue OS -> Buyer Scout timers -> Deferred Enrichment -> Review Materializer
                                      |
                                      v
                         Revenue Completion Supervisor
                                      |
             runtime/revenue_completion_supervisor/latest.json
                                      ^
                                      |
                           isolated TAM Coder lane

The supervisor is an OBSERVE/internal-runtime control surface. It does not send
email, place calls, accept terms, deploy code, move funds, confirm payments, or
recognize revenue. It reads the existing durable buyer queues, review artifacts,
and isolated TAM planner state and writes one bounded runtime snapshot.

Buyer scheduling remains owned by the existing deferred-enrichment queue. Its
priority policy rewards first-party target-person/contact evidence and applies
attempt/reason penalties so repeatedly unavailable sites cannot monopolise the
worker. Fourteen-day starvation protection remains authoritative.

A buyer is surfaced as genuinely review-ready only when the existing materializer
reports review_ready and outreach_ready and retains a preferred email plus a
decision-maker identity. Missing evidence stays UNKNOWN / blocked.

The TAM lane is monitored, not mutated. Failed or missing-worker planning is
surfaced as a blocker; completion is surfaced for the next governed build step.
