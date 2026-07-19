---
name: cortex_judge
description: Empire Cortex Judge ("The Brain") — scores Scanner patterns against the Empire Quality Rubric via REAL OpenRouter LLM (openai/gpt-4o-mini). Outputs overall + per-dimension scores (0-1) and an approval gate (threshold 0.70). If OPENROUTER_API_KEY missing it flags evaluation unreliable — never silently mock. Part of empire-cortex-swarm.service.
trigger:
  - "run the cortex judge / score the patterns"
  - scheduled: every 90s inside empire-cortex-swarm.service
---

# SKILL: cortex_judge

## What it does
`evaluate_with_ai(patterns)` -> dict:
```
{
  "overall_score": float,        # 0-1
  "visual_score": float,
  "script_score": float,
  "hook_score": float,
  "compliance_score": float,
  "approved": bool,              # overall_score >= 0.70
  "reliable": bool,              # True only if backend == openrouter
  "backend": "openrouter" | "mock"
}
```

## How to run (in-container, needs OPENROUTER_API_KEY)
```bash
incus exec empire-hub -- bash -c '
  export EMPIRE_DB=/root/empire_os/empire_os.db
  OR=$(grep ^OPENROUTER_API_KEY= /root/empire_os/.env | tail -1 | cut -d= -f2-)
  export OPENROUTER_API_KEY="$OR" LLM_BASE_URL=https://openrouter.ai/api/v1 LLM_MODEL=openai/gpt-4o-mini
  cd /root/agentic_revenue
  /root/venv/bin/python3 -c "import judge.main as J, scanner.main as S; print(J.EmpireCortexJudgeAgent().evaluate_with_ai(S.EmpireCortexScannerAgent().scan()))"'
```

## Real-vs-mock detection
- `self._ai_backend == "openrouter"` after init => REAL scores.
- Missing key => `MockGeminiClient`, `reliable: false`, score is a placeholder.
- The swarm logs `judge: scored X.XXX approved=...`. If you see "Mock Gemini"
  in logs, the key did not reach the runtime env — fix run_swarm.sh sourcing.

## Guard rails
- Real LLM only; flag unreliable if mock.
- try/except around LLM; never crash swarm.
- Scores 0-1; no "$/hr" or "wallet" language.
- No egress of eval data.
