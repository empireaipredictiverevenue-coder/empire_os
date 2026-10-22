# Smart CRM — authenticated unified workspace candidate (22 October 2026)

**STAGED, NOT LIVE.** Canonical source: EmpireDB PostgreSQL. Preserve the current `agent-kanban-crm-20261022v1` service release, Research, Jev, Startup Revenue, ASTRA, external messaging and all financial gates.

The candidate extends existing staged navigation commits `7a1166b61` and `bd70b9ab7` without a duplicate CRM. It implements **Contacts → Opportunities → Sales Actions → Conversations → Revenue** using established authenticated readers, rather than invented buyer/revenue statuses.

| Area | Existing source | Safeguards |
| --- | --- | --- |
| Contacts | Signed tenant `/v1/revenue-crm/buyers` | Buyer organisations only, not a verified contact directory or permission to contact |
| Opportunities | Signed tenant `/v1/revenue-crm/prospects` | Existing CRM rows, not promoted Scout candidates |
| Sales Actions | Existing signed per-prospect `/commercial-action-review` | Internal evidence review only, no send or status mutation |
| Conversations | Existing founder original partner/inbound/Win Plan read routes | Separate from CRM tenant identity and payable buyer claims |
| Revenue | Not yet connected to a tenant-verified settlement/order join | Held with no claimed revenue amount or checkout authority |
| Startup / Research / Jev / ASTRA | Existing specialist services remain independently governed | Startup opportunities require independently verified identity/tenant source before promotion |
| Agent Kanban | Signed tenant `/v1/revenue-crm/department-kanban` | Six known states, strict `explicit_tenant` scope, read-only, no unbound work |

Security: existing signed login; bearer in memory only, expires, HTTP 401 clears the session, no local/session storage; signed tenant-source checks; no runtime credentials or contact data written into test receipts; user strings rendered using safe `textContent`.

Validation completed: live production anonymous prospects/buyers/kanban routes HTTP 401; existing private console loopback 200 and public route 404. **27 existing CRM tenant/auth regression tests passed**, **5 candidate static tests passed**, and **synthetic Chromium signed-shaped tenant simulation passed** at mobile 390px and desktop 1440px (buyer, prospect, action and tenant task; cross-scope board rejected; signout clears content; no errors). The synthetic test does **not** prove a real founder credential sign-in or original-source end-to-end identity matching.

**Staging completed and pinned:** complete copy of the live 47MB, 2,371-file CRM backend at `/opt/empire-ai/crm-pilot-releases/smart-crm-auth-workspace-20261022v1`. All 2,369 other files match the active backend exactly; only `empire_os/static/revenue_crm_action_console.html` and `.js` differ. Candidate manifest: `/home/ubuntu/empire_releases/smart_crm_authenticated_workspace_20261022/release-manifest.json`, SHA-256 `76f6ea2f9bd4ad511bb59b4b9dbb8b7dd6d41982dbae882e1d121db084232584`; candidate tree hash `b8b245d38c2105a6a4b6a0b20e80087b286f975fd670d6bf3b6e76bb5b565295`. Source commit `3d42b47fa`.

**Activation guard prepared, not executed:** `/home/ubuntu/empire_releases/smart_crm_authenticated_workspace_20261022/activate_smart_crm_authenticated_workspace_20261022.sh --review-read-only` passed against the real active service. Activation would require **new explicit owner approval** and the separate `--apply-founder-approved` flag. Script checks pinned hashes, current root, 401 tenant isolation and public 404; swaps a single CRM systemd WorkingDirectory/PYTHONPATH drop-in, restarts only the CRM service, verifies static routes, and removes its override/restarts the old root if validation fails. The earlier Agent Kanban backend, Research, Jev, Founder Console and external website are preserved.

**Still outstanding before claiming end-to-end production:** founder's real signed-credential browser sign-in against the staged release, resulting tenant row visibility, and post-switch operational verification. Synthetic browser success is not real founder login proof. New source/identity joins for actual contacts, Startup Revenue opportunities and tenant-settled revenue require separate reviewed reader contracts and authorization. No public website or external service changes.

No database migration, tenant grants, contact/send execution, payment, published CRM route, invented opportunities or agent registration were performed.
