# Empire Coder Inference Runtime — 2026-09-21

## Hardware truth

EmpireOS currently runs on an Intel Xeon E5-1410 v2 host with 4 physical cores,
8 logical CPUs, 62 GiB RAM, AVX/SSE4.2, no AVX2 and no compute GPU.

## Current runtime

Primary planner:
- runtime: llama.cpp server
- binding: 127.0.0.1:11435 only
- model: Qwen2.5-Coder 1.5B Q4_K_M
- context: 8192
- threads: 6
- parallel slots: 1
- systemd scope: ubuntu user service
- unit: empire-llama-coder.service

Coder config routes PLAN work to llama.cpp. Larger writer work remains on the
existing specialist tier. A short live benchmark returned 32 completion tokens
from a 32-token prompt in about 3.1 seconds. That is operational evidence for
short planner work, not a general throughput guarantee.

## Reliability changes

Empire Coder now has:
1. persistent model-route health;
2. cooldown/circuit breaking after transient failures;
3. cross-process inference serialization for Ollama;
4. a loopback llama.cpp planner adapter;
5. deterministic verification independent of model inference.

Observed Ollama failures on this CPU included timeouts from 7B, 14B and 30B
routes under concurrent load. High-frequency planning therefore moved to the
smaller llama.cpp lane.

## Direction

Planner/router/classifier/incident triage:
- small local llama.cpp model.

Substantial coding/refactoring:
- queued larger model with strict concurrency;
- preferably move to a dedicated inference node.

Heavy reasoning:
- dedicated GPU/inference node or separately governed external provider.

EmpireOS should orchestrate the business rather than let large-model inference
saturate the CPU that serves acquisition, GTM, Founder Console, webhooks and
commercial-loop services.

## Security

The llama.cpp planner is loopback-only. The user service uses
NoNewPrivileges, PrivateTmp, ProtectSystem=strict and a restricted writable
path. It does not grant Coder additional production authority.
