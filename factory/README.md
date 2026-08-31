# Agentic Software Factory

LangGraph orchestrator + Aider engine + Incus sandbox for Empire OS code tasks.

## Flow
planner -> coder (Aider) -> reviewer -> tester -> verifier -> loop|done

- **planner**: repo-map scoping, picks target files (context.py)
- **coder**: LLM diff, applied via Aider (git-aware) in sandbox
- **reviewer**: LLM security/bug review
- **tester**: ad-hoc verify gate (_tester.py, sys.exit(0) pattern)
- **verifier**: loop back to coder on fail, max 3 retries

## Context engineering (the bottleneck)
- repo_map(): Aider-style tree, no body
- scope_files(): give worker ONLY needed files (no whole-repo dump)
- compress_tool_output(): truncate before re-inject
- retrieve(): RAG hook for Pinecone embeddings

## Sandbox
- run_in_sandbox(): execute worker in empire-hub via `incus exec`
- spawn_agent_container(): clone fresh container for true isolation

## Run
```bash
python3 /root/empire_os/factory/orchestrator.py "add logging to ai_email_infer"
```

## Deps
```bash
/root/venv/bin/pip install langgraph aider-chat
```
