# Runtime producers Slice 3

Diagram: dedicated EmpireDB materializer login → restricted role → observed
market aggregates; public Search Fabric (cache bypass) → current SERP evidence;
both → one Agent Web canonical snapshot → Revenue Distribution.
Existing acquisition service/timer → crawler repository → EmpireDB gateway →
atomic prospect ingestion. Opportunity Radar → evidence bridge → unchanged
11-factor formula → OBSERVE-only Revenue Distribution proposals.

Contract delta: missing crawler backend defaults to EmpireDB; explicit legacy
selection fails closed. Missing DSN cannot invoke legacy egress. Acquisition
failures remain failures and do not update last success. Agent Web replaces its
snapshot atomically only after successful current database and public retrieval;
no prior snapshot is input. SERP observations do not establish demand, revenue,
search volume, buyer intent or any formula factor.

Worker assignment: Codex implementation; verification through focused regression
checks, independent contract assertions and bounded OBSERVE execution. No service
restart, queued work, live acquisition ingestion or commercial action authorized.

Materializer: port the historical dedicated role/login contract to EmpireDB's
existing bootstrap entrypoint. Append-only writes limited to intelligence facts,
scores and supported public signals. No generic app membership. Role installation
and credentials require protected host access; preparation is not deployment.
Migration 018 is unrelated, held and unchanged. Live role/RLS and inherited PUBLIC
privilege verification remains required before provisioning on production.

Verification record (2026-09-29): 255 focused tests passed, including an isolated
PostgreSQL 18 single-user execution of the bootstrap contract twice and positive/
negative privilege checks. Changed Python modules compiled, bootstrap shell syntax
checked, and git diff --check passed. No live schema/role application occurred.

The protected canonical DSN remains unavailable to this session. The old
runtime/secrets/intelligence_materializer.env exists, but its parsed login and
database do not match the dedicated EmpireDB contract. No connection was made
with it and no credential value was printed. Producers now share canonical
protected environment loading and reject wrong login/database configurations.

Host installation entrypoint, once live role/PUBLIC privileges are reviewed:
`scripts/bootstrap_empiredb_runtime_roles.sh --intelligence-materializer`.
This uses the existing local EmpireDB endpoint, provisions only the dedicated
role/login, and atomically adds its credential to /etc/empire_os.env. It refuses
existing keys rather than silently rotating them, and refuses unsafe inherited
PUBLIC table or security-definer function authority. Live catalog reader RPCs
must exist already; this bootstrap does not create commercial RPCs or sources.
Root access, protected configuration writes and systemd bus access are unavailable
in this session. Neither the root bootstrap nor any service restart was attempted.

Safe refresh: AEO regenerated 210 assets. Agent Web failed closed before replacing
its old artifact. Radar and Revenue Distribution rebuilt: 21 opportunities,
27 proposals, 0 with evidenced factors, 0 complete 11-factor inputs, 0 calculable
revenue predictions. Search and competitor artifacts remain stale; acquisition
budget remains unknown. An existing scheduled Chicago 311 run completed with
zero candidates and no writes; it is not proof of repaired prospect ingestion.
The earlier Overpass error was legacy gateway egress, now prevented by the
crawler's explicit EmpireDB-only configuration. Live canonical acquisition proof
remains outstanding; no manual acquisition or queued execution was performed.

Checklist: diagram/contract, implementation, focused independent contract checks,
compilation, artifact rebuild and integrity hashes complete. Live role/credential
installation, live Agent Web regeneration and canonical acquisition proof blocked.
Formula SHA256 remains ed258882dd71a4292fea670807f5e5a451cdc4482f2da2204d5f6a2293e5bc2e.
Migration 018 remains e7edcfe1d0f94c3898437e68db0714557370b7b86f9b21ee76cc04be60bc3c21.
Unrelated dirty work preserved. Nothing staged or committed; authority unchanged.
