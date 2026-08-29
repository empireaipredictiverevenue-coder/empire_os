---
name: empire-adhd
description: Empire OS wrapper around UditAkhourii/adhd (Parallel Divergent Ideation). Spawns N isolated reasoning branches under different cognitive frames, then scores/prunes/deepens survivors. Use on /empire-adhd or design/architecture/naming/API/strategy decisions where linear CoT gives the first boring answer.
license: MIT
---

# Empire ADHD

Wire the ADHD repo (https://github.com/UditAkhourii/adhd) into Empire OS agents.

## What it does

ADHD treats premature convergence as an architectural problem. Spawns N isolated
reasoning processes under deliberately distorted cognitive frames (regulator,
biology, speedrunner, 10-year-old, $0 budget), with zero shared context during
divergence, then runs a separate critic pass.

## Setup

Cloned at `/root/empire_os/integrations/adhd/`. Run:

```bash
cd /root/empire_os/integrations/adhd
npm install
npm run build
```

## Use

The `SKILL.md` lives at `skills/adhd/SKILL.md`. Trigger patterns:

- `/empire-adhd <problem>` — invoke Empire OS ADHD mode
- `ideate <design decision>` — auto-detect open-ended decisions
- `fuzzy-debug <bug>` — explore non-obvious root causes

## Frames loaded

Five cognitive distortions available (from ADHD upstream):
1. regulator — compliance/safety/cost POV
2. biology — biology/physics/chemistry POV
3. speedrunner — speed/throughput/latency POV
4. 10-year-old — naive/exploratory POV
5. $0-budget — minimum cost POV

## Empire OS integration

- Calls `/v1/web/search?backend=serper` (2500/mo Google) for evidence gathering
- Calls `/v1/llm/exec` for parallel branch execution (separate context per frame)
- Aggregates scores via the critic pass
- Returns top 3 deepened survivors

## Verifier

```bash
/root/venv/bin/python3 -c "
import sys
sys.path.insert(0, '/root/empire_os/integrations/adhd')
from skills.adhd import SKILL
print('frames:', SKILL.get('frames', []))
"
```

## Cost

~10 LLM calls per /empire-adhd invocation. Use sparingly.