# EMPIRE OS LLM WIRING — Ollama Local + API Fallback

## Current State
- **MINIMAX_API_KEY** configured (env + /root/empire_secrets/minimax_api_key)
- **OPENROUTER_API_KEY** configured (env + /root/empire_secrets/openrouter_api_key)
- **No GOOGLE_API_KEY / GROQ_API_KEY / OLLAMA_HOST**

## Goal
Add **Ollama local models** for:
1. Cortex article generation (free, no rate limits)
2. ASI reflection (free, fast)
3. CEO/Business reasoning (free, privacy)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     LLM Request Flow                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Agent calls structured_chat() / chat()                     │
│                      │                                       │
│                      ▼                                       │
│  agent_core.py auto-selects:                                │
│                                                              │
│  1. OLLAMA_HOST set + reachable  → OllamaClient (local)    │
│  2. GOOGLE_API_KEY set         → GeminiClient (free tier)  │
│  3. MINIMAX_API_KEY set        → ApiClient (MiniMax M2.7)  │
│  4. OPENROUTER_API_KEY set     → ApiClient (OpenRouter)    │
│  5. None                       → _NoopLLM (rule-based)      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Steps

### 1. Install Ollama in empire-hub container
```bash
incus exec empire-hub -- curl -fsSL https://ollama.com/install.sh | sh
incus exec empire-hub -- ollama serve &
incus exec empire-hub -- ollama pull qwen2.5:7b
incus exec empire-hub -- ollama pull llama3.1:8b
incus exec empire-hub -- ollama pull gemma2:9b
```

### 2. Set OLLAMA_HOST environment
```bash
# Add to empire-hub container env
incus exec empire-hub -- systemctl edit empire-cortex-engine
# Add: Environment=OLLAMA_HOST=http://127.0.0.1:11434 LLM_MODEL=qwen2.5:7b
```

### 3. Model Assignment by Use Case

| Use Case | Model | Reason |
|----------|-------|--------|
| Cortex article_writer | qwen2.5:7b | Good at structured JSON, 8K context |
| ASI reflection | llama3.1:8b | Strong reasoning, meta-cognition |
| CEO/Business decisions | gemma2:9b | Fast, structured output |
| Innovator proposals | qwen2.5:7b | Creative + analytical |
| R&D signals | llama3.1:8b | Technical comprehension |

### 4. Cortex Engine LLM Integration
Currently cortex_engine.py uses `_NoopLLM` for `asi_pass()`. With Ollama:
- `asi_pass()` gets real LLM → `ASILayer` reflects → strategies evolve
- `run_active_aeo()` / `run_active_fix()` / `boost_hot_lanes()` use `article_writer` which uses `article_spinner._client()` → auto-selects Ollama

### 5. Verify Wiring
```bash
# Test Ollama reachable
incus exec empire-hub -- curl -s http://127.0.0.1:11434/api/tags

# Test agent_core auto-select
incus exec empire-hub -- python3 -c "
from empire_os.agent_core import OllamaClient, _ollama_reachable
print('OLLAMA_HOST:', __import__('os').environ.get('OLLAMA_HOST'))
print('Reachable:', _ollama_reachable())
c = OllamaClient()
print('Model:', c.model)
print('Chat:', c.chat(messages=[{'role':'user','content':'ping'}], temperature=0.1))
"
```

## Systemd Drop-ins for OLLAMA_HOST

Create `/etc/systemd/system/empire-cortex-engine.service.d/ollama.conf`:
```
[Service]
Environment=OLLAMA_HOST=http://127.0.0.1:11434
Environment=LLM_MODEL=qwen2.5:7b
```

Same for: empire-ceo-agent, empire-business-agent, empire-innovator, empire-rnd

## Priority After Ollama Install
1. OLLAMA_HOST set + reachable → **Ollama (local, free)**
2. GOOGLE_API_KEY → Gemini (free tier)
3. MINIMAX_API_KEY → MiniMax (paid)
4. OPENROUTER_API_KEY → OpenRouter (paid)
5. None → _NoopLLM (rule-based)

## Cost Impact
- **Ollama local**: $0/month (uses existing GPU/CPU)
- **Current**: MiniMax + OpenRouter only when needed
- **Savings**: ~$200-500/month in API calls for article generation + ASI reflection