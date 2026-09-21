# MiniMind Custom SLM Roadmap — 2026-09-21

## Purpose

Use the open-source MiniMind training stack as a future research/training
reference for Empire-specific small language models. This is a roadmap only;
it does not change production inference today.

MiniMind currently exposes from-scratch Dense/MoE training plus tokenizer
training, pretraining, SFT, LoRA, preference/RL stages and knowledge
distillation. That makes it useful as a transparent training laboratory for
specialist models rather than a replacement for Empire's model broker.

Reference: https://github.com/jingyaogong/minimind

## First Empire specialist SLMs

1. **Intent & Pain Classifier**
   - Reddit/LinkedIn/search/community text -> intent band + pain taxonomy.
   - Target: very small, fast local classifier.

2. **Why-Now Evidence Classifier**
   - Evidence bundle -> trigger relevance and timing labels.
   - Must never invent evidence.

3. **Reply/Conversation Router**
   - Inbound buyer reply -> commercial/opt-out/question/objection/routing.
   - No autonomous contract acceptance.

4. **Entity Resolution Assistant**
   - Candidate evidence -> match/ambiguous/no-match classification.
   - Canonical identity stays fail-closed.

5. **Ops Incident Classifier**
   - Logs/findings -> allowlisted incident category/playbook.
   - No raw-command authority.

6. **Search Opportunity Classifier**
   - SERP/query evidence -> commercial intent, pain theme, opportunity type.

## Training strategy

Do **not** begin by pretraining a general-purpose model from scratch.

Preferred sequence:
1. build an approved, de-identified outcome dataset from Empire evidence;
2. define deterministic labels and holdout evaluation;
3. distill from a stronger teacher into a small specialist model;
4. SFT/LoRA specialist behavior;
5. compare against deterministic baselines and current 1.5B planner;
6. only promote when precision/recall, calibration, latency and failure modes
   beat the existing route;
7. keep larger-model fallback for ambiguous cases.

From-scratch MiniMind pretraining is reserved for research/education or when
Empire owns enough domain corpus to justify a custom tokenizer/base model.

## Data governance

Training data must exclude:
- secrets and API keys;
- private customer data without appropriate authorization;
- payment credentials;
- raw sensitive records not required for the task;
- fabricated outcomes.

Every training row should retain source class, consent/usage status where
required, label provenance and dataset version.

## Infrastructure

The current EmpireOS application host is not the target training machine.
Training should run on a separate GPU worker/node. EmpireOS remains the
orchestrator and model registry.

Inference candidates that meet latency/quality targets can later be exported
into the Empire Model Broker and served locally through llama.cpp or another
approved runtime when compatible.

## Promotion gates

A specialist SLM may enter production only after:
- frozen evaluation set;
- baseline comparison;
- error taxonomy;
- confidence calibration;
- latency/resource benchmark;
- adversarial/edge-case tests;
- authority-boundary tests;
- model/version provenance;
- rollback route.
