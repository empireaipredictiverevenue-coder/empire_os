# Buyer Enrichment Adaptive Controller V1

Durable backlog + host load -> bounded capacity controller -> parallel enrichment lanes -> evidence gates -> review materializer.

The controller changes scheduling capacity only. It does not change buyer evidence, identity, suppression, commercial, call, outbound, payment, or revenue authority.

Backlog comes from the existing durable enrichment queue. Host pressure comes from local CPU count and one-minute load. Hard ceilings remain 48 candidates and 8 lanes per cycle. Elevated load reduces capacity. Small backlog shrinks work. Telemetry is recorded in each result. No retry loop or third-party dependency is added.
