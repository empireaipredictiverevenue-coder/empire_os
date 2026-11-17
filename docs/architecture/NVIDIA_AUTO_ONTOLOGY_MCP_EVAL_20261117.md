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


## 2026-11-17 — Resolved OpenCode V2 OAuth discovery failure

**Incident reported by founder:** `bash scripts/authorize_existing_nvidia_mcp_viewer_20261117.sh`
previously stopped at:
`Issuer mismatch in authorization server metadata (RFC 8414 §3.3)`:
OpenCode expected `http://localhost:33000/` but NVIDIA returned
`http://localhost:33000/api/auth`. No user OAuth token had been issued.

**Verified root cause #1 — wrong advertised issuer:**
Pinned NVIDIA MCP `build_auto_ontology_auth` published the frontend root
`settings.api_url` as its RFC 9728 authorization server, while the
upstream Better Auth OAuth issuer is `{api_url}/api/auth`.
NVIDIA's actual authorization metadata confirmed this exact path.
Added `scripts/nvidia_mcp_verified_issuer_20261117.py` to resolve and
verify the upstream canonical issuer before starting the *original pinned
FastMCP server*. Only `mcp.auth.authorization_servers` is updated.
The vendor source, opaque token verifier, caller identity forwarding,
tools and authenticated frontend are not modified. The guard refuses
unexpected endpoints, scopes, or non-loopback production routes.

Activated via
`scripts/activate_nvidia_mcp_issuer_fix_20261117.sh` on the **existing
unprivileged MCP user service only**, with a private rollback of its
former unit at `runtime/nvidia_ontology_eval/mcp-unit.pre-issuer-fix-20261117.service`
(mode 0600). Existing systemd service `empire-nvidia-ontology-mcp-eval.service`
restarted once and reached active/running, zero unexpected restarts.
Live protected-resource metadata now advertises
`authorization_servers=["http://localhost:33000/api/auth"]`, matching
the issuer in NVIDIA's real OAuth metadata exactly. Unauthenticated
and invalid bearer MCP access remain HTTP 401. The NVIDIA frontend,
Postgres, ingestion, free model gateway, and running OpenCode service
were not restarted by this correction.

**Verified root cause #2 — OAuth-only metadata misread as OpenID:**
The Better Auth `mcp({ disableJwtPlugin: true })` setting intentionally
uses opaque, immediately revocable OAuth bearer tokens, and its
standards-conforming OAuth metadata does not include a signing-key
`jwks_uri`. After correcting the issuer, the OpenCode V2 client then
raised `invalid_type` for missing `jwks_uri` during automatic discovery.
Do **not** invent a JWKS endpoint, bypass signature validation, or
silently switch NVIDIA to JWT bearer tokens.

OpenCode V2's supported
`mcp.servers.nvidia-auto-ontology.oauth.auth_server_metadata_url`
configuration explicitly selects the existing RFC 8414 OAuth-only
discovery URL:
`http://localhost:33000/api/auth/.well-known/oauth-authorization-server`.
Reference: `https://opencode.ai/docs/mcp-servers` (OAuth settings).
In a temporary, private OpenCode V2.3.0 test server, that single setting
advanced to `Authorization started`, `Authorize ... in your browser`
and `Waiting for authorization` without either metadata failure.
No interactive login was completed in this preflight.

Applied that **single MCP metadata hint** to BOTH the persistent
OpenCode V2 config and the already-running V2 service's existing overlay,
using `scripts/apply_nvidia_opencode_oauth_metadata_20261117.py`.
Private pre-change backups created in each directory as
`opencode.pre-oauth-metadata-20261117.json`. Both configs remain
owner-private mode 0600; all other configured agents, permissions,
models and concurrent owner edits are preserved. OpenCode service
remained PID 2631346; no restart.

**Actual original OpenCode process verified after fixes:**
The same original interactive viewer-login helper was invoked in a
bounded, headless preflight (`BROWSER=/bin/false` and timeout) with
a mode-0600 private log. It reached both
`Authorization started` and `Waiting for authorization` and had
**no issuer mismatch, no missing JWKS error, and no auth failure**.
The test was deliberately cancelled without any viewer sign-in;
no authorization link, callback code or token was shared in chat.
The running OpenCode V2 CLI continues to recognise the MCP server
as `needs authentication`.

New independent readback:
`runtime/nvidia_ontology_eval/nvidia_opencode_viewer_gate_20261117_v2.json`,
preserving the previous v1 receipt. It reports:
`status=OPENCODE_V2_MCP_BOUND_VIEWER_OAUTH_REQUIRED`,
`nvidia_issuer_matched=true`,
`oauth_metadata_url_is_explicit=true`,
`browser_oauth_stage_reached_without_schema_errors=true`,
`unauthenticated_vendor_mcp_http=401`,
`existing_service_pid_unchanged=true`,
`authenticated_viewer_tool_invocation=false`,
`tenant_isolation_verified=false`.

**Tests and release boundary:**
- 11 issuer-guard tests plus 88 pinned upstream MCP tests: **99 PASS**.
- Existing EmpireOS integration/NLP regression suite: **41 PASS**.
- No authenticated viewer tool call, production tenant test or new agent
  release was claimed.
- Next human step: run the **existing** sign-in helper from EmpireOS,
  `bash /srv/empire_os/scripts/authorize_existing_nvidia_mcp_viewer_20261117.sh`,
  and complete the real browser OAuth sign-in as an explicitly approved
  NVIDIA Viewer. If accessing localhost from another machine, use the
  existing authorised private browser/SSH tunnel; do not paste OAuth
  callback URLs, codes, passwords or tokens into the conversation.
- Once the viewer signs in, verify `opencode mcp list` shows connected,
  then authenticate and call the pinned `check_readiness`,
  `search_terms`, `ask_question` tools against the synthetic graph
  and verify deny cases. Tenant isolation remains a separate gate.

**Status:** Both OAuth metadata incompatibilities repaired,
OpenCode interactive authorization handoff **verified**, authenticated
viewer execution **pending user sign-in**. No fake JWKS, no app rebuild.


## 2026-11-17 — Remote Windows browser "site can't be reached" fixed

The user opened NVIDIA's OAuth authorization URL from an ApexEngine
Windows browser while OpenCode and NVIDIA were bound to localhost on the
remote EmpireOS Ubuntu host. On EmpireOS, `http://localhost:33000/login`
returned HTTP 200 and `/api/health` returned ok; no public website outage
occurred. The OAuth redirect had a random loopback callback port, which
also would have failed from the separate Windows browser.

**Actual corrective action, not just advice:**

- The account-linked Desktop Commander device **apexengine** was online;
  it runs Windows PowerShell and had an existing authenticated SSH
  configuration alias `empire` for EmpireOS. SSH public-key authentication
  with `BatchMode=yes` passed. No credentials were copied or printed.
- OpenCode V2's supported `oauth.callback_port` was set to **33018** for
  only `mcp.servers.nvidia-auto-ontology`, in both its existing
  persistent and current service configurations. Source:
  `scripts/pin_nvidia_opencode_oauth_callback_20261117.py`.
  All other settings, models, agents and permissions were preserved at
  write time. Private 0600 rollback files
  `opencode.pre-ssh-oauth-callback-20261117.json` were saved beside
  each original. No agent or NVIDIA service was restarted.
- A bounded headless **real OpenCode V2 OAuth attempt** proved the
  authorization page uses `http://localhost:33000/api/auth/oauth2/authorize`
  and the redirect points to `http://127.0.0.1:33018/callback`.
  Both the issuer mismatch and JWKS errors remained absent. This was
  **not** a successful login; no user's OAuth code or token was consumed.
- A private, SSH-authenticated Windows **port-forward tunnel** was started
  on apexengine using the original `empire` SSH host alias, with
  `BatchMode=yes`, `StrictHostKeyChecking=yes`,
  `ExitOnForwardFailure=yes` and loopback-only mappings
  `127.0.0.1:33000 -> EmpireOS 127.0.0.1:33000` and
  `127.0.0.1:33018 -> EmpireOS 127.0.0.1:33018`.
  Local tunnel process PID and an SSH diagnostic log reside in the user's
  private Windows `%LOCALAPPDATA%\EmpireAI\NvidiaMcpOAuthTunnel\`.
  No public listeners and no new firewall rules were added.
- **Windows-origin HTTP proof:** browser-machine request for
  `http://localhost:33000/login` returned **HTTP 200**, and
  `http://localhost:33000/api/health` returned **ok**.
  Both 33000 and 33018 Windows loopback listeners were observed. During
  a fresh bounded OAuth attempt, the Windows-origin GET to
  `http://127.0.0.1:33018/callback` reached the active remote callback
  handler and returned **HTTP 400 for the intentionally absent OAuth
  code/state** — confirming the network callback route actually works,
  without consuming or exposing a real authorization token.
- Final Windows readback: SSH tunnel process `ssh.exe` **alive**, loopback
  ports 33000 and 33018 listening, NVIDIA browser login HTTP **200**.
  Existing EmpireOS MCP endpoint remains authentication-protected.

**Remaining identity gate:** On the original EmpireOS terminal rerun
`bash /srv/empire_os/scripts/authorize_existing_nvidia_mcp_viewer_20261117.sh`.
Open the freshly generated authorization URL in the **Windows** browser
(with its tunnel still running) and complete interactive sign-in using an
approved Viewer identity. Do **not** paste the authorization code, state,
callback URL, password or token into ChatGPT. The earlier headless OAuth
tests were intentionally cancelled; only a real signed-in viewer can
authorise MCP tool invocation and complete the identity gate.

The private SSH tunnel is only needed during the login flow. After user
sign-in, stop its known saved PID from Windows; do not widen the exposed
frontend. Signed-in tool invocation and tenant-isolation verification
remain separate release gates.
