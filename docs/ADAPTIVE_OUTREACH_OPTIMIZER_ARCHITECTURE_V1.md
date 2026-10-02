# Adaptive Outreach Optimizer Architecture V1

## Goal

Automatically rotate and learn first-touch email subject/body copy from real
Empire outbound outcomes while preserving all existing review, suppression,
personhood, daily-cap and sender-authority gates.

## Canonical flow

review-ready buyer
-> evidence-safe copy generator
-> subject arms + body arms
-> adaptive selector
-> selected arm IDs stored in outbound intent metadata
-> existing governed outbound approval/send
-> provider delivery events + classified replies in EmpireDB
-> outcome compiler
-> derived performance snapshot
-> next adaptive selection

## Learning signal

Primary learning is based on canonical delivered email and classified replies.

Commercial-conversation classes:
- positive
- question
- objection
- later

Stop classes:
- negative
- unsubscribe

Open tracking is not used to choose winners. Bounces are tracked for
deliverability but do not score copy effectiveness because recipient quality is
not copy quality.

## Assignment

Subject and body are independently assigned so their marginal performance can
be learned without creating a large combinatorial experiment.

Cold start:
- deterministic balanced assignment using the existing experiment engine;
- no winner is declared before minimum delivered samples exist.

Adaptive stage:
- exploit the best evidence-backed arm for most recipients;
- retain a deterministic exploration slice so alternatives continue learning;
- prefer a niche/offer/decision-role segment only when that segment has enough
  observations, otherwise fall back to global evidence.

## Guardrails

- generated variants must pass the existing message quality rules;
- no invented prospect pain, demand, urgency, proof, relationship or revenue;
- no fake Re:/Fwd: first touch;
- one primary CTA;
- opt-out/footer remain mandatory;
- no change to send authority, daily cap, review authority or suppression;
- derived optimiser state is non-canonical; EmpireDB events/replies remain truth;
- insufficient evidence is represented as LEARNING, never as a claimed winner.

## Initial production truth

At build time, the recent 60-day history contains 123 intents and only four
classified replies, all unsubscribe. Existing messages were not consistently
arm-labelled, so historical data is shown as baseline context but is not used
to falsely attribute performance to the new arm IDs.

## Authority

The optimiser may select copy only. It cannot approve an intent, bypass a
suppression, create commercial terms, request payment or recognize revenue.
