# EmpireOS CRM046 — suppression-hit closure

**Scope approved by founder:** one restricted, tenant-authorised, read-only SMS suppression-hit PostgreSQL function. Not approval for contact export, general CRM credentials, broad reader grants, email/SMS delivery, campaign launch, paid traffic, payment, or future migrations.

## Technical release

- SQL: `migrations/empiredb/046_crm_prospect_suppression_hit.sql`
- One-time deployer: `scripts/deploy_empiredb_crm046_suppression_hit.sh`
- Real isolated PostgreSQL acceptance: `bash scripts/test_crm046_isolated_fixture.sh`
- Safety tests: `tests/test_crm046_suppression_release.py`
- Existing CRM adapter: `empire_os/revenue_crm_suppression_evidence_reader.py`
- Existing UI channel preview: `/v1/revenue-crm/prospects/{prospect_id}/channel-evidence-preview`

The function is SECURITY DEFINER, STABLE, search_path locked, owned by empiredb_migrator, EXECUTE restricted to the existing NOLOGIN tenant CRM reader role. The caller's trusted session_user tenant and prospect binding must match. There is no raw phone/contact return, global table SELECT grant, outbound write, scheduled send, or marketing eligibility claim. Unsupported, malformed, unsuppressed, and cross-tenant queries return only UNKNOWN. A canonical suppressed E.164 phone can return SUPPRESSED, which creates a block.

The isolated PostgreSQL 18 fixture proved: two separate tenant-bound sessions; same-tenant suppression blocks, cross-tenant never exposes a hit, unsupported channel stays unknown, no-hit stays unknown, raw contact and global suppression SELECT permissions absent, public function grant absent. The fixture creates and drops its own throw-away PostgreSQL cluster; it never connects to empiredb.

## Approved one-time deployment

Production source status: **prepared and tested; do NOT mark deployed without the operator's receipt**.

```bash
cd /srv/empire_os
sudo -n bash scripts/deploy_empiredb_crm046_suppression_hit.sh \
  --apply --approved-046-suppression-only
```

The deployer verifies git-committed SQL source, local PostgreSQL 18 canonical cluster, configured application DSN same DB, prerequisites, backup capacity, SHA256-verified full backup plus globals, atomic migration, privilege/owner readback and a negative UNKNOWN test. No restart or API activation.

Expected final receipt: `CRM046_STATUS=FUNCTION_DEPLOYED_NOT_MARKETING_ELIGIBILITY`. If it reports BLOCKED/FAILED or a post-commit warning, **do not retry blindly**; reconcile the result and preserve the private error log. Backup integrity validation is included; a full restore rehearsal is not claimed.

## Stop building unrelated CRM features

CRM visual designer, bounded journey draft persistence code, and channel evidence preview remain separate code-complete capabilities. Version storage migration 045, tenant logins, channel/purpose-specific verifiable consent, and a production authenticated principal remain separately gated. This release is specifically a suppression blocker, not permission to contact anyone. Once the operator receipt is verified, close 046 and move attention back to buyer/publisher revenue execution rather than starting another CRM version.
