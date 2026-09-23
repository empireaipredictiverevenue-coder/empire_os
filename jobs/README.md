# Empire Hermes Control Queue

This branch is a governed control plane for the resident Hermes worker.

- `jobs/inbox/*.json` contains immutable job requests.
- `jobs/results/*.json` is written by EmpireOS after execution.
- Code changes are never merged from this branch.
- Hermes works in isolated disposable worktrees and publishes successful
  proposals to `hermes/job-<job_id>`.
- Production merge, live outbound, payments, database mutation, authority
  expansion, recovery/ and toop/ are outside this queue's authority.
