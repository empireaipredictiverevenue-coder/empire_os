# Skill: master-dominant-agent
# Description: Empire OS Master Dominant Multi-Strategy Agent with 7 modules + Ollama LLM
# This skill integrates the complete dominant agent system (relay server, waterfall ingestor,
# gauntlet loop copy engine, closed loop learning, rate limiter, self-healing diagnostics)
# into the Empire OS agent ecosystem. It connects to Ollama LLM for Gauntlet critic assistance
# and orchestrates all other Empire OS agents for maximum ROI.

name: master-dominant-agent
description: |
  Empire OS Master Dominant Multi-Strategy Agent — the core orchestration engine
  that integrates all 7 modules (relay server, waterfall ingestor, gauntlet loop,
  closed loop learning, bulletproof rate limiter, self-healing diagnostics) with
  Ollama LLM integration for AI-powered copy generation and critique.

core_modules:
  - relay_server: Twenty CRM webhook receiver on port 3000 + Resend email SDK
  - waterfall_ingestor: Multi-niche scraping → pgvector deduplication → Twenty CRM REST API
  - gauntlet_loop: Sub-agents + critic → iterate until hyper-personalized copy approved
  - closed_loop_learning: Capture successful replies → pgvector → daily copy refinement
  - bulletproof_rate_limiter: Redis token-bucket · per-endpoint limits · exponential backoff
  - self_healing_diagnostics: Pattern detection → auto-fix → error statistics
  - ollama_llm: llama3.1:8b + qwen3.5:9b integration for critic assistance

dependencies:
  - nodejs v22.23.1 (for JS modules)
  - python3 v3.12.3 (for Python Empire OS agents)
  - ollama v0.32.15 with llama3.1:8b + qwen3.5:9b models
  - redis (for rate limiter)
  - supabase/postgresql (for closed loop learning pgvector)
  - twenty-crm access (for relay/webhook)
  - resend SDK (for email outreach)

setup: |
  1. Install Node.js dependencies: cd /root/empire_os && npm install
  2. Install Python dependencies: pip install redis pg google-api-python-client requests
  3. Start Ollama: ollama serve
  4. Pull models: ollama pull llama3.1:8b && ollama pull qwen3.5:9b
  5. Configure secrets: cp /root/.empire_secrets/social.env.example .env (add Twenty CRM, Resend, Supabase)
  6. Initialize Redis: redis-server --daemonize yes
  7. Start the master agent: node /root/empire_os/scripts/master_dominant_agent.js

execution: |
  node /root/empire_os/scripts/master_dominant_agent.js

royot_metrics:
  - gauntlet_approved_copy_rate: % of gauntlet loops that produce approved copy
  - closed_loop_refinement_rate: % of successes captured and feeding back into refinement
  - rate_limiter_efficiency: requests processed vs. rate limited (target >95%)
  - self_healing_recovery: % of errors auto-fixed without human intervention
  - overall_conversion: leads processed → emails sent → meetings booked → revenue

best_practices: |
  - Keep Ollama models warmed up (periodic generate calls)
  - Monitor Redis rate limiter metrics during high-volume periods
  - Log all gauntlet iterations for quality analysis
  - Capture every success in the closed loop (never skip)
  - Test self-healing patterns regularly to expand auto-fix library
  - Maintain 200 OK on Twenty CRM webhooks immediately (before processing)

category: empire-os
tags: [agent, orchestration, ollama, ai, empire-os, dominant, multi-strategy, gauntlet, learning-loop, rate-limiter, self-healing]