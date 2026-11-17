# Empire AI / NVIDIA Auto Ontology — native MCP evaluation

Date: 2026-11-17
Owner: `agent/data-cloud-wave4`
Scope: existing **isolated synthetic** `empire-nvidia-ontology-eval` stack on EmpireOS.

## Verified deployment

- **Existing vendor MCP, not a duplicate:** original pinned NVIDIA
  `runtime/nvidia_ontology_eval/vendor/mcp`, package version 1.2.0,
  installed in private evaluation venv `runtime/nvidia_ontology_eval/.mcp_venv`.
  FastMCP 3.4.11, MCP SDK 1.30.0, PyJWT 2.15.1. Pinned vendor MCP tests:
  **88 passed**. No change to NVIDIA source or its application containers.
- Existing owner-managed **systemd --user** service:
  `empire-nvidia-ontology-mcp-eval.service`.
  Canonical config:
  `deploy/systemd-user/empire-nvidia-ontology-mcp-eval.service`.
  Active `ubuntu` service unit is a symlink to the tracked file.
- Binds **only** `127.0.0.1:33013` and advertises
  `http://127.0.0.1:33013/mcp`. No public proxy, external listener,
  privileged helper, root service, admin cookie, shared bearer, or
  new paid inference route.
- Vendor MCP talks to the already-running authenticated NVIDIA frontend at
  `http://localhost:33000`. The frontend talks to the already-verified
  isolated synthetic SQLite fixture. Its four canonical terms and the
  six verified executed NLP-to-SQL benchmark cases remain unchanged.
- The service runs with no new privileges, strict read-only system files,
  read-only home, private temporary directory, restricted address families,
  a 512 MB memory limit, 50% CPU quota, and an up to 180-second MCP chat
  timeout. Service observed active/running, zero restarts, ~83 MB memory,
  and expected loopback listener.

## Actual live authentication and tool discovery

Executed `scripts/probe_nvidia_mcp_existing_20261117.py` against the
**running MCP endpoint** and actual NVIDIA OAuth provider.

Private receipt:
`runtime/nvidia_ontology_eval/nvidia_mcp_live_auth_boundary_20261117.json`
(owner mode 0600, not in Git).

| Check | Result |
| --- | --- |
| MCP HTTP without bearer | 401 |
| MCP HTTP with an invalid bearer | 401 |
| MCP HTTP with an unrecognised API key | 401 |
| NVIDIA OAuth userinfo with invalid bearer | 401 |
| MCP protected-resource metadata | HTTP 200 |
| MCP resource identifier | Exact `http://127.0.0.1:33013/mcp` |
| OAuth authorization-server discovery | Verified, registration endpoint present |
| OAuth `openid` scope | Advertised |
| Exact intended tool list | 9/9 available |
| Tool descriptions | All present |

The **nine upstream tools** are:

`check_readiness`, `search_terms`, `check_answerable`,
`ask_question`, `get_term`, `get_term_columns`,
`get_term_sql_attributes`, `get_sql_attribute`, `describe_table`.

The tool-surface test is an in-process inspection of NVIDIA's
`FastMCP` object, alongside live HTTP authentication rejection tests.
It is **not** a claim that an authenticated agent has executed a remote
MCP tool. Upstream authorisation checks and per-user CallerAuth are
maintained rather than replaced with an EmpireOS master key.

Regression:
- NVIDIA upstream MCP tests: **88 PASS**.
- EmpireOS targeted NVIDIA/MCP + six NLP benchmark tests: **38 PASS**,
  one unrelated pre-existing Starlette deprecation warning.
- No production identity, customer data, payment, email or buyer-route
  changes made by MCP deployment.

## Agent-connection and release gates

OpenCode is already running on EmpireOS under its own installed service and
Orca has active agent workspaces. The active OpenCode configuration was
**inspected read-only** and deliberately not modified. That preserves the
existing owner configuration, current agent sessions and approved tools.

To bind an existing *authenticated* agent to this endpoint, the agent's
MCP-capable client should use the URL
`http://127.0.0.1:33013/mcp` **from the EmpireOS host** and complete
NVIDIA's OAuth authorization-code login against the loopback frontend.
Each agent should authenticate as the lowest-privileged existing approved
viewer/user. Do **not** paste or inject `AUTO_ONTOLOGY_ADMIN_PASSWORD`,
reuse the founder administrator browser cookie, or configure a shared
OpenRouter/API key in the MCP server.

**Not yet verified / intentionally held:**

1. A real existing agent client completes an interactive OAuth login and
   calls `check_readiness`, `search_terms`, then `ask_question`
   through MCP as an explicitly permitted viewer.
2. A viewer is unable to call administrator routes, access unbound tenants,
   or read another user's conversations. The synthetic fixture alone is
   not tenant-isolation proof.
3. Verified per-user signed-in MCP call audit/evidence lineage is correlated
   with existing EmpireOS agent/Smart CRM owner before production.
4. Remote access is not provided. Neither MCP nor the NVIDIA frontend
   is public; remote browsers or agents require a separately approved
   private access route and the approved OAuth identity.
5. Automatic semantic recompilation remains disabled, as the earlier native
   background compile never reached a success receipt.
6. No production data, buyer verification, outbound, payments,
   recognised revenue or external launch are authorised by this evaluation.

**Release taxonomy:** native MCP endpoint **implemented and running**;
HTTP/OAuth metadata and anonymous-denial **verified**; nine tool
definitions **verified**; signed-in agent tool invocation **not verified**;
tenant security and production release **held**.

No further MCP server or OS redesign is warranted by this stage. Preserve
this single local vendor server and finish identity-bound agent acceptance
before changing the current OpenCode/Orca sessions.


## 2026-11-17, current OpenCode V2 / Orca connection

**Completed and verified in the original, running OpenCode V2 service:**

- OpenCode V2.3.0 executable:
  `/home/ubuntu/.local/share/empire-opencode-v2-isolated/node_modules/@opencode/cli/bin/opencode.exe`.
  Original service PID `2631346`, started 13 November, remained unchanged;
  **no OpenCode or EmpireOS service restart**.
- Existing OpenCode V2 persistent config:
  `/home/ubuntu/.config/empire-opencode-v2/opencode/opencode.json`.
  Original exact JSON backed up privately as
  `opencode.pre-nvidia-mcp-20261117.json` (0600). The sole additive
  change is `mcp.servers.nvidia-auto-ontology` with
  `type=remote`, `url=http://127.0.0.1:33013/mcp`.
  OpenCode V2 uses nested `mcp.servers`, *not* V1's flat map, and
  defaults to connected when `disabled` is absent. Existing models,
  agent/persona configuration, permissions and policies preserved.
- OpenCode's *already running* managed service uses a separate
  `XDG_CONFIG_HOME=/tmp/empire_opencode_v2_free_20261113/config`.
  Its active service config previously contained no MCP entry. Added
  the same minimal MCP-only configuration to the existing service's
  `config/opencode/opencode.json` (0600); service's auth config,
  providers, models and agents were not modified. This private active
  overlay matches the persistent source's single NVIDIA entry.
- Another owner concurrently added a `compaction` field to the
  persistent config. This was **preserved**; tests assert the original
  pre-existing keys remain exactly unchanged without blocking independent
  current-owner additions.
- Validated current V2 MCP format with V2's own `opencode mcp add`
  in a **temporary isolated test config**, followed by a running test
  server with its own short-lived local credential (no production
  restart). On a warmed server, the native V2 CLI correctly reported
  `nvidia-auto-ontology needs authentication`.
  The first `mcp list --standalone` call on a cold test server showed
  an empty registry; the warmed response and original live service are
  authoritative, not the cold-start output.
- Queried **the original live V2 service** using its own existing
  service credential, loaded privately from
  `/tmp/empire_opencode_v2_free_20261113/config/opencode/service.json`.
  The native `opencode.exe mcp list --server http://127.0.0.1:49374`
  displays `nvidia-auto-ontology needs authentication`.
  No shared NVIDIA administrator session or token was supplied.
- Vendor MCP remains on loopback `127.0.0.1:33013`, returns HTTP
  401 without OAuth and advertises a valid OAuth protected resource.
  The NVIDIA application remains healthy at loopback `33000`.
- Evidence script:
  `scripts/verify_nvidia_opencode_viewer_gate_20261117.py`.
  Private immutable receipt:
  `runtime/nvidia_ontology_eval/nvidia_opencode_viewer_gate_20261117.json`
  (0600):
  `status=OPENCODE_V2_MCP_BOUND_VIEWER_OAUTH_REQUIRED`;
  `open_code_cli_listing_pass=true`;
  `unauthenticated_vendor_mcp_http=401`;
  `restart_performed=false`;
  `credential_or_token_disclosed=false`;
  `authenticated_viewer_tool_invocation=false`;
  `tenant_isolation_verified=false`.
  The default-location OpenCode HTTP status and CLI's explicit workspace
  status can represent different locations; for the active workspace,
  the authenticated V2 CLI is the acceptance authority.
- Created `scripts/authorize_existing_nvidia_mcp_viewer_20261117.sh`.
  This is an **interactive sign-in helper**, not an automatic identity
  bypass. It reuses the current V2 service and locally held service
  credential to request the native OAuth sign-in, explicitly unsets
  bootstrap administrator environment fields and never writes an OAuth
  code/token into Git or ChatGPT.

**Regression:** 41 EmpireOS targeted tests passed, plus 88 pinned
vendor MCP tests from the earlier stage; one unrelated Starlette
deprecation warning.

**Outstanding, explicitly NOT claimed:**

1. An approved NVIDIA **viewer** identity completes the OAuth browser
   sign-in within the *existing OpenCode V2 agent session*.
2. Under that viewer identity, `check_readiness`,
   `search_terms` and `ask_question` return actual MCP tool results
   and exact synthetic database evidence.
3. A viewer cannot execute admin routes or read another person's
   conversation or unbound tenant records. The single-tenant synthetic
   fixture is insufficient to verify production tenant isolation.
4. Production customer data, agent publication, financial actions,
   outbound contact, inference spending and real-revenue claims remain
   unchanged and unauthorised.

**User-controlled completion (only when the existing permitted viewer
can sign in):** In the EmpireOS/Orca terminal run:

```bash
bash /srv/empire_os/scripts/authorize_existing_nvidia_mcp_viewer_20261117.sh
```

Follow the normal OAuth browser sign-in using the approved viewer account.
If signing in from a separate laptop, localhost web/OAuth endpoints must
be reached through the user's existing authorised SSH port-forward or
private connection. Do not paste any authorization codes, callback URLs,
passwords or access tokens into chat. No root access is required.

This is a **genuine human/identity gate**, not an infrastructure rebuild.
