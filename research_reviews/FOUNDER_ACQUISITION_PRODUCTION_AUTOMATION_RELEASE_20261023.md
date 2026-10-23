# EmpireOS founder acquisition — native business automation release
2026-10-23 | This is NOT a ChatGPT scheduled task. The original Buyer Acquisition Team timer remains the sole cadence.
Original native cadence: empire-buyer-acquisition-team.timer, existing systemd 5-minute OnUnitInactiveSec. No new timers, process daemons or agents.

## Existing authority, source and behavior
* Integration lives in the existing empire_os/buyer_acquisition_team.py refresh_buyer_acquisition_plan(). It uses a bounded subprocess via the SAME executable / same root, after writing the existing acquisition plan, without affecting the standard plan on read failure.
* The new scripts/run_founder_acquisition_review.py consumes seven original sent Gmail message IDs (Plena, Alloovium, Libra Robotics, Acolite, Qlo, Propaya, Andco) and the verified existing founder shortlisting CSV. It uses the installed GoogleWorkspaceMailboxProvider (existing service credential/expected account), never a new OAuth secret.
* Only Gmail metadata is read. Complete seven-thread anchored verification is required. Incoming exact sender/company-domain observations are pending HUMAN review, never commercial buying proof or independent SMTP delivery proof.
* The existing 16-prospect CSV is the duplicate-safe company backlog. Seven contact records have exact Gmail sent IDs, including Plena's special separate receipt; ten prospects remain unsent. Additional source-verified candidates can be appended without inheriting mail approval. No automatic acquisition sends; this is source/evidence-to-review automation.
* Private snapshot: runtime/founder_acquisition/founder_reply_review_latest.json, mode 0600 and parent mode 0700, with original provider message IDs only. No raw bodies, RFC email addresses, thread subjects or credentials retained. Previous inbound candidate IDs must not silently disappear.
* Outputs ALWAYS report false on CRM writes, outbound execution, paid pilot commitments, revenue verification and payment activation. Signed canonical EmpireDB tenant/suppression approval still required before any fresh one-to-one outreach. Existing producer logic cannot be converted to an unrestricted sender by founder email text.

## Live activation order
1. Commit this release to isolated feature branch and run tests using the existing /srv/empire_os/.venv/bin/python.
2. Confirm production buyer_acquisition_team.py matches the exact pre-release feature base. Do not modify scripts/refresh_buyer_acquisition_team.py, which has other agents' uncommitted edits.
3. Copy only four code/test files (autopilot module, runner, integration module and tests) plus exact verified 16-company CSV into original /srv/empire_os; reject if unknown files exist or source base changed.
4. Verify production code compiles, invoke the read-only runner with --write, then invoke refresh_founder_acquisition_observer('/srv/empire_os') and see status SEVEN_FOUNDER_THREADS_REVIEWED; do not start a second timer or restart unrelated services.
5. Confirm existing timer remains enabled, and private snapshot exists with 0600; observe next scheduled run.
6. Commit ONLY the newly owned files and integration module in production, without staging or resetting any other uncommitted multi-agent work. The isolated feature branch owns the historical research and send receipts.

## Hold and rollback
An invalid CSV, missing provider account, unverified sent anchor, missing prior inbound record, unknown snapshot permissions, mailbox API outage, or untrusted response must HOLD without sending. Original buyer acquisition refresh continues.
If rollback requested, revert the scoped integration commit using the existing owner's change procedure, or remove only the additional function call and newly owned files after preserving snapshot evidence. Do not reset /srv/empire_os and do not touch unrelated dirty worktrees, timer files, outbounds, databases or payments.
