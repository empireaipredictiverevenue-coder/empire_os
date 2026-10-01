# Revenue Distribution producer Slice 3

Diagram: existing public Search Fabric → competitor search presence;
canonical Agent Web producer (not located) → canonical_snapshot.json;
run_acquisition_cycle → crawler_runner → acquisition/latest.json;
existing producer artifacts → Opportunity Radar → evidence bridge → locked
Predictive Revenue formula → Revenue Distribution (OBSERVE proposals only).

Contract delta: explicit producer errors/status failures must be rejected even
when a timestamp is fresh. No new producer, database role, or factor inference.
Implementation worker: Codex. Verification: focused regression tests and safe
artifact rebuild; live producer limitations recorded separately.

Inspection: competitor refresh requires the dedicated materializer even without
persistence because it reads resolved business_entities through that role.
The process and readable runtime/secrets/outbound.env lack the dedicated key.
/etc/empire_os.env and /etc/empiredb.env are unreadable under current permissions;
key presence there is unknown. Bootstrap requires authorized configuration of
EMPIRE_INTELLIGENCE_MATERIALIZER_DSN for the existing dedicated transport and
resolved entity reader. No substitute credential is permitted.

Agent Web canonical_snapshot.json has consumers but no producer located in the
repository or inspected service definitions. Leave its timestamp unchanged until
the canonical export producer and its authorized source are available.

Crawler already uses the canonical acquisition/latest.json. Existing scheduled
runs may refresh it; manually running run_acquisition_cycle invokes ingestion,
not a read-only observation refresh, so do not expand authority to run it here.
The artifact's booleans describe observed events, not numeric supply counts.

Verification: 208 focused tests passed; changed Python files compiled;
git diff --check passed. Locked formula has no diff; Migration 018 matches
required SHA256. AEO census freshly read 210 assets. Radar/Distribution rebuilt:
21 opportunities, 26 proposals, zero evidenced factors, revenue unknown.
A subsequent scheduled crawler run returned ok=false, returncode=1 (Overpass;
timeout marker in captured output). Its evidence remains unavailable. No manual
crawler ingestion, service restart, persistence, staging, commit or activation
performed. Search and competitor refresh remain blocked as described above.
