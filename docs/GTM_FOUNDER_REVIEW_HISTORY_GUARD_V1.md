# GTM Founder Review History Guard V1

Founder-review routing now checks canonical outbound history before a buyer can
appear in the founder-review queue.

Guard order:
1. prior outbound history by prospect;
2. prior outbound history by recipient domain;
3. exact recipient suppression.

Statuses treated as prior contact include sending, sent, delivered, replied,
suppressed, bounced, and failed. If history cannot be read, founder-review
routing fails closed for that row.

This guard does not expand standing authority or send anything. It only prevents
duplicate founder-review candidates from resurfacing.
