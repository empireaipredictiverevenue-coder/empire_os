# Empire Data Exchange V16 — Temporal Evidence and Review

Scope: existing first-party EmpireDB V15 OBSERVE custody and V14 Signal Board.

V15 genesis is in production at sequence 0 with the recorded local SHA256
head c7c3b13bde6684168e07fc9af17c19b8183d8b43c7de5930fa55814210ae4f1c.
One canonical snapshot does not establish a historical change or buyer intent.

V16 adds three bounded components:
- data_exchange_temporal_quality.py recomputes existing custody proofs,
  checks the three pinned official UK Planning Data identifiers, and
  grades temporal separation, recency, and sample membership.
- review_data_exchange_v16_temporal.py reads the existing dedicated
  custody connection only. Optional recheck performs a fresh official
  GET using the same existing fixed-source adapter.
- operate_data_exchange_v16_followup.py defaults to a read-only
  eligibility check and offers a separately founder-gated, manual,
  one-shot canonical append through the already-deployed V15 transport.

A meaningful second historical observation requires at least 24 elapsed
hours from the latest stored observation. More than 90 days' separation
cannot automatically extend this reviewed chain. A current snapshot older
than 72 hours is stale for current-source readiness.

A source GET that agrees with the stored record is repeat-source
corroboration, NOT independent authentication or a government signature.
A source disagreement is a HOLD requiring another canonical snapshot.
Missing sampled entities are not deleted development sites.
Only the three fixed identifiers are in scope; regional market coverage
is unknown. A window of 16 observations without genesis is not a
full-origin chain proof.

The existing V14 board is reused for any source field transition.
The source licence, field-level commercial rights, buying intent,
prediction accuracy, customer delivery, resale, payment and outbound
remain unverified and unauthorised.

No new database, migration, timer, service, network scanner, model
dependency, customer feed or scheduled automation is introduced.

Operational readiness: the first stored observation is live. V16 can
evaluate that record read-only. A second real observation, and thus
a genuine change-comparison result, requires a later manual source
capture meeting the elapsed-time gate. Never manufacture one for tests
or claim one has been persisted without the canonical DB receipt.
