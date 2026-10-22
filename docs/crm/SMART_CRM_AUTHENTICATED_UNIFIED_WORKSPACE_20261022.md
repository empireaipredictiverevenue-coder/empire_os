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

Next: pin and stage a complete copy of the currently live 47MB, ~2371-file CRM backend release with only the two static console files changed. Before any live deployment, perform a fresh source-drift check, review a rollback override, obtain scoped approval, restart only `empire-revenue-crm-pilot.service`, then independently verify live signed founder login, existing endpoints, tenant isolation and rollback. No public website or external service changes.

No database migration, tenant grants, contact/send execution, payment, published CRM route, invented opportunities or agent registration were performed.
