# CRM search evidence connection — implementation checkpoint

Status: scope validation implemented; database and HTTP integration pending.
Production activation: not authorised by this document.

## Observed boundary

Founder-provided EmpireDB catalog capture confirms seo_sites has id,
tenant_key and base_url, but no canonical entity or UUID tenant link.
prospect_entity_links connects prospects to business_entities.
tenant_business_entity_bindings holds evidence-backed, time-limited tenant
scope. The displayed grants give empire_search_reader SELECT on search sites,
backlinks and AI visibility; the capture does not prove all effective grants.

The inspected CRM authorization function uses session-derived tenant identity
and requires exactly one eligible prospect/entity/binding join. Observed-only
bindings are excluded. The existing search repository uses a configured text
tenant_key. Neither a request tenant key nor a matching website establishes
CRM authority.

## Required flow

Authenticated CRM principal -> existing authorised prospect/entity resolution
-> explicit tenant/entity/site evidence binding -> restricted observation read
-> existing growth brief builder.

The new revenue_crm_search_scope module validates server-loaded mapping rows.
It is not authentication and must never receive binding records from an HTTP
payload. Its tenant and authorised entity arguments come from trusted CRM
resolution. The request may select prospect/site IDs but cannot authorise them.

## Database delta to prepare and verify

Prepare a separately reviewed, initially empty tenant/entity/site binding
relation in EmpireDB. Required values: tenant UUID, entity UUID, site UUID,
search tenant key at approval, binding evidence reference, active flag,
valid-from and optional valid-until. Use existing entity/site foreign keys.
Pin the approved site identity (including base URL) or revoke the binding on
identity changes; a mutable site URL must not silently redirect authority.
Do not seed bindings by matching domain names, and do not cast tenant_key to
the CRM tenant UUID. Genuine owner evidence is required for provisioning.

Prepare a bounded restricted reader following the existing trusted session
tenant foundation. It must independently recheck CRM prospect authorization,
exact entity identity, binding validity, site identity and tenant-key match
within the same read-only transaction as observation selection. The Python
validator is defence in depth, not the database access boundary.

Do not grant the CRM reader access to the global binding tables or membership
in empire_search_reader. The intended narrow reader returns tenant_id,
prospect_id, entity_id, site_id, binding provenance and only the selected site's
observations. Select query/engine before limiting citation rows; return explicit
truncation metadata. Sanitize errors without hiding unavailable evidence.

Authenticated route outcomes must distinguish unauthenticated, unauthorized,
not connected, connected with no observations, connected with observations,
and reader unavailable. The existing caller-supplied preview remains a preview.
Neither empty results nor a valid binding proves rankings, revenue or citations.

## Required verification before activation

Scope unit tests cover cross-tenant/prospect/entity/site rejection, duplicate
current bindings, revocation, expiry, future validity, malformed provenance and
timezones. Eight local cases pass. These tests do not prove PostgreSQL isolation.

Next: prepare SQL and integration against an isolated copy of the authenticated
CRM source. Run real ephemeral PostgreSQL login tests for tenants A/B, unbound
login, forged tenant settings, forbidden raw-table access, revocation between
requests, site identity changes, empty observations and failed reads. Reuse the
existing CRM login tests and restricted role checks. Verify migration rollback
and current live catalog/policies before requesting production activation.

Shared /srv/empire_os has concurrent edits including CRM transport; do not
overwrite them. This checkpoint is a separate draft scope-validation slice,
not a claim that the account evidence reader or wider SEO programme is complete.
