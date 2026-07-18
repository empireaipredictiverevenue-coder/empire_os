# Code Review — Skill Spec

Used by the Code Review Agent (`code_review_agent.py`) when LLM-reviewing
each scanned file. Goal: surface ONLY actionable, real findings.

## What to FLAG (with severity)

- **S1 — breaks prod**
  - `py_compile` / import failure
  - unhandled exception on a hot path (request handler, charge flow)
  - wrong function/API signature vs call site
  - `return None` where caller expects a value
- **S2 — leaks / loses data**
  - secret written to a non-secret file or logged
  - DB write outside a transaction / no rollback
  - f-string SQL / unparameterized query
  - unvalidated external input reaching `eval`/`exec`/`os.system`/subprocess
  - unbounded loop that can OOM
- **S3 — smell**
  - function > 60 lines doing 3 jobs
  - magic number used for a threshold/config
  - duplicated logic copy-pasted across agents
  - bare `except:` / `except Exception: pass` swallowing errors
  - hardcoded path that should be config

## What NOT to flag

- Style: naming, line length, import order (S5)
- Missing docstrings/type hints unless S1/S2 risk (S4)
- Opinions about architecture unless it causes S1/S2
- Things already caught by `py_compile`/import (those are auto-filed; don't
  duplicate as LLM findings)

## Output contract

Strict JSON only:

```json
{"verdicts": [
  {"file": "empire_os/charge.py",
   "line": 112,
   "severity": 2,
   "fix": "use parameterized query / mail_sender._send not raw smtp"}
]}
```

- Max 5 verdicts per cycle.
- If file is clean, return `{"verdicts": []}`.
- Never include secrets in `fix` text (auto-redacted anyway).
