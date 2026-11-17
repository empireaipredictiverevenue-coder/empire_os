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
