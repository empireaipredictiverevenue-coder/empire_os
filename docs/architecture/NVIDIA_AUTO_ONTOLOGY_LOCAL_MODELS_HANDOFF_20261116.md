# NVIDIA Auto Ontology — local AI integration handoff (2026-11-16)

## Verified local components

- Existing EmpireOS Ollama 0.34.2 is operational on host loopback
  `127.0.0.1:11434`. No Ollama daemon restart or exposure.
- Local coder model `qwen2.5-coder:1.5b` answered an OpenAI-compatible
  chat request. A namespaced alias `openai/qwen2.5-coder:1.5b`
  references the **same** 986MB Ollama model digest, letting NVIDIA
  select its `ChatOpenAI` client rather than NVIDIA-hosted `ChatNVIDIA`.
- Installed `nomic-embed-text` into existing Ollama (274MB). Verified
  NVIDIA's embedding extras (`input_type`, `truncate`, `modality`)
  through OpenAI-compatible `/v1/embeddings` API: outputs 768 dimensions.
- Added local-only allowlisted gateway at
  `/srv/empire_os/scripts/nvidia_ontology_local_model_gateway_20261116.py`,
  running under **existing ubuntu systemd --user**, no root privileges.
  Service: `empire-nvidia-ontology-local-model-gateway.service`.
- Single source of service definition:
  `deploy/systemd-user/empire-nvidia-ontology-local-model-gateway.service`.
  The active user service is a symlink to this file.
- Gateway binds `172.18.0.1:19999` only (the private NVIDIA Docker
  network's host bridge); no listener on the public host interface.
  It forwards only `/v1/chat/completions`, `/v1/embeddings` and read-only
  `/v1/models` to local host Ollama. The model IDs are allowlisted.
  Requests over 1MB, streaming requests, unapproved paths/models and
  sources outside local bridge/loopback are rejected. Four simultaneous
  inference requests maximum. No prompt contents logged.
- Verified `GET /health` and both live chat and embedding routes through
  the gateway. The user systemd service reports active, zero restarts.
- Verified Python gateway / isolated Compose / native NVIDIA connector
  targeted regression suite: **20 tests passed**.

## NVIDIA Docker configuration

Under `/srv/empire_os/runtime/nvidia_ontology_eval`:

- Current `.env` (0600) now points reasoning, non-reasoning and embedding
  model endpoints at `http://172.18.0.1:19999/v1`.
- Chat model: `openai/qwen2.5-coder:1.5b`.
- Embed model: `nomic-embed-text`.
- `RERANK_ENDPOINT` remains disabled (`127.0.0.1:19999/v1` inside
  the container); local reranking has **not** been implemented/verified.
- Model API keys remain non-paying dummy values. No NVIDIA or other remote
  provider credentials are configured.
- Exact original environment is preserved at
  `.env.disabled-models-20261116` (0600). No secrets copied into Git.
- Existing private Docker topology and synthetic SQLite source are unchanged:
  only frontend has loopback-published host port `33000`.
- The running Docker backend and ingestion have **not yet been restarted**
  to load the revised environment. Runtime success must not be claimed yet.

## Prepared guarded activation

Operator file `runtime/nvidia_ontology_eval/activate_local_models_and_capture.sh`
requires a single `sudo bash` invocation from the existing EmpireOS
terminal; it deliberately does not grant Docker group privileges.

Preflight: exact Docker plugin digests, resolved Compose project/network,
port and synthetic-source isolation; gateway health; a real embedding request
**from inside the existing NVIDIA ingestion container**, and a real model
request **from inside the existing NVIDIA backend container**. If either
fails, all containers stay unchanged and the readback records the error.

Only if both network canaries pass does the script run:

```bash
docker compose up -d --no-deps --no-build --pull never ingestion-service auto-ontology
```

It verifies that the PostgreSQL and frontend container IDs did not change,
captures HTTP health, logs and status in the existing private runtime folder.

Actual founder command once preflight tests are complete:

```bash
sudo bash /srv/empire_os/runtime/nvidia_ontology_eval/activate_local_models_and_capture.sh
```

Do not paste environment variables or secret-bearing outputs. Review
`local_models_activation_readback.txt` directly using the connected
remote file capability.

## Remaining proof gates after activation

1. Container-to-host gateway model requests pass in both Docker namespaces.
2. Ingestion successfully embeds the four synthetic tables without retries;
   vector count and dimensions verified in the evaluation-only metadata DB.
3. Semantic compilation explicitly enabled with **authorised application
   login**, and compiled terms verified against the six canonical
   buyer-demand graph benchmarks; do not bypass application authentication.
4. A first-party NLP query returns matching SQL and source values; wrong
   or unanswerable questions do not manufacture verified buyer, revenue or
   capacity claims.
5. MCP server still separate from upstream Compose; it must have proper
   OAuth and tool results tested before declaring autonomous agent integration.

All real customer routing, revenue, tenant binding, outbound and deployment
gates remain unchanged. This integration only ingests synthetic fixtures.
