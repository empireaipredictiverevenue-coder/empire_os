# Offer Contact Holding Bridge Architecture V1

## Goal

Convert already-observed, first-party person-bound commercial-offer contacts
into Buyer Scout holding candidates without bypassing canonical prospect
promotion or outbound governance.

## Flow

commercial offer contact recovery
-> exact person/email first-party evidence
-> same-domain check
-> MX validation
-> canonical suppression check
-> Buyer Scout holding candidate
-> existing review-readiness gate
-> founder-governed raw-prospect promotion
-> canonical prospect
-> buyer candidate review
-> GTM/outbound gates

## Admission rules

A contact may contribute evidence only when:
- the person is explicitly named;
- the email is directly bound to that person in the source artifact;
- source URL host equals candidate company domain;
- email domain equals candidate company domain;
- email has MX and is neither role nor disposable;
- email is not in canonical outbound suppressions.

Cross-domain relationships are blocked unless separately reconciled. This keeps
H.I.G. Growth / hig.com out of automatic promotion.

## Holding candidate truth

- direct_buyer_score=0 means no explicit direct-inventory-buying signal observed;
- buy_signal_score is not created here and remains UNKNOWN/NULL on any later raw
  prospect promotion;
- first-party contact evidence and ready product codes are preserved;
- holding persistence grants no outreach, commercial, payment, or revenue
  authority.

## Gate

Canonical raw-prospect promotion remains founder-governed. This bridge stops at
the holding/review-ready boundary unless an explicit founder promotion gate is
present.

## Authority

Internal reversible holding-area write only. No canonical prospect promotion,
outbound send, terms acceptance, payment action, or revenue recognition.
