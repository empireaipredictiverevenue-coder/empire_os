# EmpireOS buyer intent — open-source enhancement review (14 October 2026)

**Programme:** sovereign first-party rapport → reply evidence → intent evaluation → graded CTA → human closer review → independently verified sales outcome. **Do not install another orchestration/runtime or route prospect data to external services.** Zero spend; no autonomous sends.

## Source-verified open-source shortlist

| Project and licence | Applicable ideas | EmpireOS decision |
| --- | --- | --- |
| [Hugging Face SetFit](https://github.com/huggingface/setfit), Apache-2.0 | Small-data text classification and sentence-transformer fine tuning | **Research candidate after** enough consented and human-labelled REAL prospect replies, with model/weights licence checks and local inference benchmarking. Do not train on synthetic ground truth as though it were real buying behaviour. No install today. |
| [spaCy](https://github.com/explosion/spacy), MIT | Token-aware phrase/negation matching; deterministic recognizers | **Lightweight concepts adopted without copying code.** Current first-party regex engine sufficient for 42-case negative-control regression; benchmark before optional dependency installation. |
| [Promptfoo](https://github.com/promptfoo/promptfoo), MIT | Adversarial prompts and repeatable safety/quality suites | Useful design reference, but EmpireOS **already has** `typed_decision_eval`, `benchmark_laya_shadow`, regression gauntlets. Do NOT create a second evaluation framework. |
| [Presidio](https://github.com/data-privacy-stack/presidio), MIT (formerly under Microsoft GitHub) | PII redaction/anonymisation before model evaluation and annotated datasets | High value **future offline/privacy study**, not an urgent new service. Verify tenant-bound reversible vs irreversible redaction, email/thread preservation and added load before integrating. Redaction alone cannot guarantee all PII is found. |
| [Argilla](https://github.com/argilla-io/argilla), Apache-2.0 | Human labelling, disagreement review and annotated intent examples | Research-only. Maintainers state **feature development is not continuing** and seek additional maintainers; our existing first-party evidence/review system is preferable until we have actual human-labelled cases. |

Source licences are as displayed by their repositories on 14 October 2026; **dependency/model/data licences must be verified separately** before adoption. No external code or third-party endpoints added.

## What was engineered today

- Original positive CTA matcher depended on presence of a named product plus a purchase word. This can mistake **refusals, paraphrases and counterfactual quotations** for actual buying requests.
- Added conservative `PURCHASE_COUNTERINTENT` evidence checks to the EXISTING `rapport_intent_cta._corroborates`; explicit refusal and hypothetical/quoted purchase examples now hold for manual review even when AI reports high confidence.
- Added **42 wholly synthetic labelled first-party cases**, covering all four intent labels and 18 non-purchase examples in `benchmarks/rapport_intent_cases.jsonl`. This is a TEST SET, **not** training labels, real sales performance, calibration evidence or permission to activate AI.
- Added `tests/test_rapport_intent_negative_controls.py` to check non-purchase controls cannot pass even a deliberately optimistic text-only purchase classifier, and that the existing `typed_decision_eval` can evaluate the labelled fixture without activating a provider.
- Targeted regression suite: **221 passed**. This verifies code invariants on synthetic inputs, **not** runtime true-positive/false-positive rates.

## Production gates and future order

1. Keep the founder professional-mailbox/canonical-reply work with its existing agent. No duplicate code paths or contact sends.
2. Build a protected, consent-appropriate set of **human-reviewed actual email replies** using current canonical IDs, preserving tenant isolation and opt-out. Do not copy names/emails into public benchmark artifacts.
3. Run existing `typed_decision_eval` for local Laya/Qwen/any future classifier with separate, withheld evaluation samples, confusion matrix, *purchase-class precision*, quote/negation false-positive count, confidence calibration, p95 latency and timeout rate.
4. Optional future local SetFit experiment only once usable real labelled sample sizes exist. Resident model smoke tests of four fictional messages on 14 October showed Laya **3/4 correct, all confidence <0.85**; Qwen 1.5B **3/4 timeouts, one misclassification**. Neither promoted.
5. Human-only explicit verified purchase enquiry remains available for **review** when AI underperforms; current catalog price and scope must be verified independently, sending separately authorised.
6. Do not treat fixture accuracy, positive reply sentiment, mailbox opens or a sales conversation as an accepted purchase, payment or earned revenue.

**Mode:** code-only, no deployment, new dependency, credential change, database write, model activation, SMTP, buyer email or payment.
