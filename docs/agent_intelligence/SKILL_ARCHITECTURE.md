# Empire Native Skill Architecture

## Flow

Founder / Astra
→ Agent Constitution
→ SOUL
→ Persona
→ Agent Contract
→ Skill Router
→ Skill Graph
→ Model Router
→ Execution Plane
→ Independent Verifier
→ Outcome Evaluator
→ Knowledge Garden

## Separation of concerns

SOUL:
persistent identity, principles and judgment.

Persona:
specialist expertise, quality bar, anti-patterns and decision behaviour.

Skill:
progressively loaded executable knowledge for a bounded task.

Authority:
independent runtime permission controlling side effects.

Verifier:
independent evidence-based evaluation.

Knowledge Garden:
candidate learning and governed promotion.

## Initial native skill families

- architecture-first
- production-truth
- evidence-truth
- git-verification
- python-backend
- pytest-debugger
- nextjs-engineer
- cinematic-frontend
- visual-qa
- responsive-qa
- supabase
- crawler-engineering
- seo-aeo
- revenue-intelligence
- revenue-truth
- buyer-policy-evidence
- buyer-conversation
- commercial-exchange
- systemd-production
- security-review

Existing skills should be reused or wrapped where suitable rather than copied.

## Skill Graph

Skills can declare:

requires
recommends
verifies_with
conflicts_with

Graph edges select knowledge, not authority.

Example:

cinematic-frontend
  requires: nextjs-engineer
  recommends: brand-guidelines
  verifies_with: visual-qa, responsive-qa

buyer-activation
  requires: buyer-policy-evidence, revenue-truth
  verifies_with: commercial-verification

systemd-production
  verifies_with: production-verification

## Promotion

Candidate
→ schema validation
→ static evaluation
→ regression evaluation
→ independent review
→ ACTIVE

No skill self-promotes.
