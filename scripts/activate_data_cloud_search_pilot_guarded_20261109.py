"""One bounded owner publisher. No actions on import; --preflight is read-only.

Operator evidence is mandatory, independently digest pinned, root owned, and
fresh. See the focused provenance note for its schema and the pristine-source
constraint. Never prints command output, environment values or credentials.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import pwd
from pathlib import Path
import re
import secrets
import shlex
import shutil
import signal
import subprocess
import time
import urllib.request
import urllib.error

ROOT = Path('/home/ubuntu/empire_worktrees/data_cloud_source_provenance_review_20261109')
BASE = '900b0ee6d4c08266f8ff39e97bd846f210a40457'
BRANCH = 'feature/data-cloud-source-provenance-review-20261109'
CANONICAL = Path('/srv/empire_os')
OLD = Path('/opt/empire-ai/data-cloud-founder-pilot-20261107')
NEW = Path('/opt/empire-ai/data-cloud-founder-search-20261109-v1')
STATE = Path('/var/lib/empire-data-cloud-search-owner-20261109')
RECEIPT = STATE / 'OWNER_RECEIPT.json'
JOURNAL = STATE / 'JOURNAL.json'
OVERLAY = Path('/etc/systemd/system/empire-public-gateway.service.d/zzzzzzzzzzzz-data-cloud-founder-search-20261109.conf')
SERVICE = 'empire-public-gateway.service'
CRM = 'empire-revenue-crm-pilot.service'
OLD_SHA = 'c233b9011fb015991841d2e94c4fbfe99e2d71d30beb01c9cc4929df1b7259ac'
PYTHON = '/srv/empire_os/.venv/bin/python'
ENTRY = 'data_cloud_public_entrypoint_20261107.py'
FLAGS = ('EMPIRE_DATA_CLOUD_FOUNDER_SEARCH_RELEASE', 'EMPIRE_DATA_CLOUD_SEARCH_RECEIPT_SHA256')
FUNCTIONS = {
    'authenticate': 'text', 'usage_snapshot': 'text',
    'reserve': 'text,text,text,text,text', 'settle': 'text,bigint,text,bigint,text',
}
ROLE = 'empire_data_cloud_meter_login'
# These are READ observations, not approval of dirty canonical modifications.
# Owner evidence must separately approve these exact collector bytes/dependencies.
COLLECTOR = {
    'empire_os/search_fabric/__init__.py': 'ddd6b62428f29efc477e660de16a36167ae321ab0f0096beab4f8d7ad45e0734',
    'empire_os/search_fabric/search.py': '3b1ba5599088283d308de66ef17226fb1109e54bbc7cad1f0aafbfdd62acb2f9',
    'empire_os/search_fabric/public_fallback.py': 'c3d4fc80eeaf5dd541e0f8dc433e38aef2167eaabe19d54f803d91bb999170a4',
    'empire_os/search_fabric/decoder.py': '457f09457bb55d1634136632d35c366d6c903bfc7b13d09cc892815044bb8b5f',
    'empire_os/search_fabric/safe_metadata_v56.py': '7789e606bf4ca195684fa11f8a5614465ab01474a12429ae84ce4f03395eee8a',
    'empire_os/geo_registry.py': '76e2a10524eff6a41e4d424db17c27ec7002c5274564a939a2de2d6f12912603',
    'empire_os/locale_intelligence.py': '4500c7c8aca4e834f6dab4df7ad685747a5cac2e01402bc389546d6e9ae48613',
}
PACKAGE = (
    'empire_os/predictive_cloud_search_release.py',
    'empire_os/predictive_cloud_route_assembly.py',
    'empire_os/predictive_cloud_founder_session.py',
    'empire_os/predictive_cloud_gateway_attestation.py',
    *('empire_os/predictive_cloud_customer_api/' + n for n in (
        '__init__.py', 'SOURCE_PROVENANCE.json', 'gateway_candidate_entrypoint.py',
        'durable_api.py', 'durable_store.py', 'private_api.py', 'empiredb_metering_adapter.py')),
)
REQUIREMENTS = frozenset({
    'owner_lease_verified', 'founder_only_path_verified', 'signed_data_session_verified',
    'production_meter_role_verified', 'production_meter_functions_verified',
    'rollback_preflight_verified', 'fresh_local_restore_receipt_verified',
    'dba_sql_and_acl_acceptance_verified', 'existing_gateway_rollback_verified',
    'billing_and_paid_provider_calls_disabled', 'source_egress_and_rights_reviewed',
    'production_meter_write_functions_verified',
})
LIVE_REQUIREMENTS = {
    'founder_only_path_verified', 'production_meter_role_verified',
    'production_meter_functions_verified', 'production_meter_write_functions_verified',
}

USAGE_RECEIPT = Path('/var/lib/empire-data-cloud-founder-pilot/RELEASE_EVIDENCE.json')
OWNER_APPROVALS = frozenset({'founder_search_authorized', 'source_egress_and_rights_reviewed',
                             'dba_search_sql_and_acl_accepted', 'billing_and_paid_provider_calls_disabled'})


def require(value, code):
    if not value:
        raise RuntimeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def run(args, data=None):
    # An explicit clean environment prevents inherited PGPASSWORD/PGSERVICE etc.
    result = subprocess.run(args, input=data, capture_output=True, timeout=45,
                            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C',
                                 'PYTHONDONTWRITEBYTECODE': '1'})
    require(result.returncode == 0, 'operator_command_failed')
    return result.stdout.decode().strip()


def db(sql):
    return run(['runuser', '-u', 'postgres', '--', 'psql', '-X', '-qAtw',
                '-v', 'ON_ERROR_STOP=1', '-d', 'empiredb'], sql.encode())


def protected(path, *, root=True, source_uid=None):
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)),
            'symlink_or_relative_path')
    require(path.is_file(), 'required_file_missing')
    st = path.stat()
    forbidden = 0o002 if source_uid is not None else 0o022
    require(not st.st_mode & forbidden and (not root or st.st_uid == 0)
            and (source_uid is None or st.st_uid == source_uid), 'unprotected_file')
    return path.read_bytes()


def write_new(path, raw, mode=0o444):
    require(not path.exists() and not path.is_symlink(), 'refuse_existing_file')
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.chown(path, 0, 0)
    os.chmod(path, mode)


def checkpoint(value):
    # An interrupted checkpoint must never block the recovery checkpoint.
    # Unique exclusive temp names avoid reusing a stale .journal-next file.
    tmp = STATE / ('.journal-next-' + secrets.token_hex(8))
    try:
        write_new(tmp, encode(value), 0o600)
        os.replace(tmp, JOURNAL)
    finally:
        if tmp.exists():
            tmp.unlink()
    fd = os.open(STATE, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def source(release_commit):
    require(Path.cwd().resolve() == ROOT and ROOT.resolve() == ROOT, 'exact_worktree_required')
    require(re.fullmatch(r'[a-f0-9]{40}', release_commit or ''), 'release_commit_required')
    require(run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']) == release_commit, 'head_changed')
    run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', BASE, release_commit])
    require(run(['git', '-C', str(ROOT), 'branch', '--show-current']) == BRANCH, 'branch_changed')
    require(not run(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=all']),
            'source_not_pristine')
    files = {}
    for name in (*PACKAGE, 'scripts/' + ENTRY):
        actual = protected(ROOT / name, root=False,
                           source_uid=pwd.getpwnam('ubuntu').pw_uid)
        blob = run(['git', '-C', str(ROOT), 'hash-object', '--stdin'], actual)
        require(blob == run(['git', '-C', str(ROOT), 'rev-parse', BASE + ':' + name]),
                'source_hash_changed')
        files[name.removeprefix('scripts/')] = actual
    for name, digest in COLLECTOR.items():
        raw = protected(CANONICAL / name, root=False,
                        source_uid=pwd.getpwnam('ubuntu').pw_uid)
        require(sha(raw) == digest, 'collector_bytes_unapproved')
        files[name] = raw
    return files


def service_snapshot(service):
    def show(prop):
        return run(['systemctl', 'show', service, '-p', prop, '--value'])
    require(run(['systemctl', 'is-active', service]) == 'active', 'prior_service_inactive')
    fragment = show('FragmentPath')
    drops = shlex.split(show('DropInPaths'))
    require(fragment and len(drops) == len(set(drops)), 'unit_inventory_invalid')
    paths = [fragment, *drops]
    hashes = {p: sha(protected(Path(p))) for p in paths}
    env = show('Environment')
    values = dict(s.split('=', 1) for s in shlex.split(env) if '=' in s)
    # Hash environment, never put its potentially secret values in receipts/logs.
    env_files = show('EnvironmentFiles')
    env_hashes = {}
    require(not re.sub(r'\S+ \(ignore_errors=(yes|no)\)', '', env_files).strip(),
            'environment_files_not_understood')
    for path, optional in re.findall(r'(\S+) \(ignore_errors=(yes|no)\)', env_files):
        require(path not in env_hashes, 'duplicate_environment_file')
        target = Path(path)
        if optional == 'yes':
            require(service in (SERVICE, CRM), 'unknown_optional_environment_service')
        if not target.exists() and not target.is_symlink():
            require(optional == 'yes' and target.is_absolute()
                    and not any(p.is_symlink() for p in target.parents),
                    'required_environment_file_missing')
            digest = None
        else:
            digest = sha(protected(target, root=False))
        env_hashes[path] = dict(optional=optional == 'yes', sha256=digest)
    execution = show('ExecStart')
    argv = re.search(r'argv\[\]=(.*?) ;', execution)
    executable = re.search(r'path=(.*?) ;', execution)
    require(argv is not None and executable is not None, 'execstart_format_unproven')
    return dict(exec=dict(path=executable.group(1), argv=shlex.split(argv.group(1))),
                unit_files=hashes, dropins=drops,
                environment_sha256=sha(env.encode()), environment_files=env_hashes,
                other_environment_sha256=sha(encode({k: v for k, v in values.items()
                                                     if k not in (*FLAGS, 'PYTHONPATH',
                                                                  'PYTHONDONTWRITEBYTECODE')})),
                bytecode_disabled=values.get('PYTHONDONTWRITEBYTECODE') == '1',
                pythonpath=values.get('PYTHONPATH', ''),
                search_values={k: values[k] for k in FLAGS if k in values},
                working_directory=show('WorkingDirectory'))


def validate_overlay_baseline(snapshot):
    require(not snapshot['search_values'], 'search_already_configured')
    require(str(OLD) in snapshot['pythonpath'].split(':'), 'old_release_pythonpath_missing')
    require(str(NEW) not in snapshot['pythonpath'], 'new_release_already_configured')
    require(all(Path(p).name < OVERLAY.name for p in snapshot['dropins']),
            'search_overlay_not_strictly_last')
    # Inspect every active override, not just the known Data Cloud owner file.
    for p in snapshot['unit_files']:
        raw = protected(Path(p)).decode()
        require(not any(flag in raw for flag in FLAGS), 'search_override_collision')
        require(str(NEW) not in raw, 'release_override_collision')
    args = snapshot['exec']['argv']
    require(snapshot['exec']['path'] == args[0], 'execstart_path_changed')
    suffix = ['data_cloud_public_entrypoint_20261107:app', '--host', '127.0.0.1',
              '--port', '80', '--workers', '1']
    require(args in [
        [PYTHON, '-m', 'uvicorn', *suffix],
        ['/srv/empire_os/.venv/bin/uvicorn', *suffix]], 'original_execstart_changed')


DB_QUERY = """SELECT jsonb_build_object(
 'version',current_setting('server_version_num')::int,
 'database',current_database(),'operator',current_user,
 'roles',(SELECT jsonb_agg(to_jsonb(r) ORDER BY rolname) FROM
   (SELECT rolname,rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,
     rolreplication,rolinherit FROM pg_roles WHERE rolname IN
     ('empire_data_cloud_api_owner','empire_data_cloud_meter_login')) r),
 'memberships',(SELECT count(*) FROM pg_auth_members m JOIN pg_roles r
   ON r.oid=m.member WHERE r.rolname='empire_data_cloud_meter_login'),
 'tenants',(SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY tenant_id),'[]')
   FROM empire_data_cloud_api.tenants t),
 'keys',(SELECT jsonb_build_object('total',count(*),'active',count(*) FILTER
    (WHERE active AND expires_at>now()),'tenants',jsonb_agg(tenant_id ORDER BY tenant_id))
    FROM empire_data_cloud_api.api_keys),
 'functions',(SELECT jsonb_agg(jsonb_build_object(
    'name',p.proname,'args',oidvectortypes(p.proargtypes),
    'owner',pg_get_userbyid(p.proowner),'definer',p.prosecdef,
    'config',p.proconfig,'body',p.prosrc,
    'execute',has_function_privilege('empire_data_cloud_meter_login',p.oid,'EXECUTE'),
    'acl',(SELECT jsonb_agg(to_jsonb(a) ORDER BY grantee,grantor,privilege_type)
       FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a))
    ORDER BY p.proname) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
    WHERE n.nspname='empire_data_cloud_api'))::text"""


def database():
    return json.loads(db(DB_QUERY + ';'))


def validate_database(state):
    require(state['database'] == 'empiredb' and state['operator'] == 'postgres'
            and 180000 <= state['version'] < 190000, 'canonical_pg18_required')
    roles = state['roles']
    require(len(roles) == 2 and state['memberships'] == 0, 'dedicated_roles_unproven')
    for role in roles:
        require(not any(role[k] for k in ('rolsuper', 'rolbypassrls', 'rolcreaterole',
                                         'rolcreatedb', 'rolreplication', 'rolinherit')),
                'unsafe_meter_role')
        require(role['rolcanlogin'] == (role['rolname'] == ROLE), 'role_login_changed')
    tenants = state['tenants']
    require(len(tenants) == 1, 'one_founder_tenant_required')
    t = tenants[0]
    require(t['active'] is True and t['held'] is False and
            'search' not in t['allowed_operations'] and
            'site_audit' not in t['allowed_operations'], 'founder_entitlement_changed')
    require(state['keys'] == dict(total=1, active=1, tenants=[t['tenant_id']]),
            'one_existing_active_key_required')
    # The existing founder usage-only tenant has zero budget. Its original
    # SQL requires a 1-micro-dollar RESERVED ceiling for each direct public
    # search even though the actual PAID provider fee is independently 0.
    # Allow only the exact three-request original zero-budget preimage; the
    # owner transaction grants 3 micros of INTERNAL reservation headroom,
    # never paid provider access or actual spending authority.
    require(t['monthly_request_cap'] == 3
            and t['monthly_cost_cap_micros'] == 0
            and t['search_cost_ceiling_micros'] == 1,
            'founder_search_internal_reservation_preimage_changed')
    funcs = state['functions']
    require(len(funcs) == 4 and {f['name'] for f in funcs} == set(FUNCTIONS),
            'function_inventory_changed')
    sql = (ROOT / 'docs/release_candidates/empire_data_cloud_meter_pg18_review_only_20261107.sql').read_text()
    for f in funcs:
        body = re.search(r'FUNCTION empire_data_cloud_api\.' + f['name'] +
                         r'\(.*?AS \$\$(.*?)\$\$;', sql, re.S)
        require(body is not None and f['body'] == body.group(1), 'live_function_body_changed')
        require(f['args'].replace(' ', '') == FUNCTIONS[f['name']] and f['definer'] is True
                and f['owner'] == 'empire_data_cloud_api_owner'
                and f['config'] == ['search_path=pg_catalog, empire_data_cloud_api'],
                'function_security_changed')
        require(f['execute'] == (f['name'] in ('authenticate', 'usage_snapshot')),
                'original_function_acl_changed')
    return t


def http(method, path, port=80):
    # Loopback only, no proxy, no redirects, no credentials or response bodies.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request('http://127.0.0.1:' + str(port) + path, method=method)
    try:
        with opener.open(request, timeout=4) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def smoke(paths, search):
    expected = [('GET', '/v1/data/usage', 401), ('POST', '/v1/data/search', search),
                ('POST', '/v1/data/site-audits', 404)]
    for path, code in paths.items():
        require(path.startswith('/') and not path.startswith('//') and '?' not in path
                and code in (200, 401, 403, 405), 'unrelated_route_evidence_invalid')
        expected.append(('GET', path, code))
    for method, path, code in expected:
        require(http(method, path) == code, 'gateway_http_baseline_failed')
    require(http('GET', '/health', 8783) == 200, 'crm_prior_backend_unhealthy')
    return {method + ' ' + path: code for method, path, code in expected}


def owner_evidence(path, digest):
    require(re.fullmatch('[a-f0-9]{64}', digest or ''), 'evidence_digest_required')
    raw = protected(path)
    require(sha(raw) == digest, 'owner_evidence_digest_changed')
    evidence = json.loads(raw)
    require(re.fullmatch(r'[a-f0-9]{40}', evidence.get('head', ''))
            and evidence['collector_files'] == COLLECTOR, 'source_approval_missing')
    require(0 <= time.time() - evidence['checked_at'] <= 86400, 'owner_evidence_not_fresh')
    require(len(evidence['unrelated_paths']) >= 3, 'other_gateway_owners_not_covered')
    require(evidence.get('scope') == 'FOUNDER_ONLY_FIRST_PARTY_SEARCH_NO_PAID_API'
            and all(evidence.get('approvals', {}).get(k) is True for k in OWNER_APPROVALS),
            'explicit_owner_search_authorization_missing')
    # Existing receipt and live checks supply facts; unknown approvals stay missing.
    reference = evidence['usage_receipt']
    require(reference['path'] == str(USAGE_RECEIPT), 'unexpected_usage_receipt')
    # The ORIGINAL already-activated usage receipt is private ubuntu-owned
    # mode 0600, not root-owned; its SHA is independently pinned in the new
    # root-owned owner evidence. Preserve its authentic existing custody.
    raw = protected(USAGE_RECEIPT, root=False, source_uid=pwd.getpwnam('ubuntu').pw_uid)
    require(sha(raw) == reference['sha256'], 'usage_receipt_digest_changed')
    receipt = json.loads(raw)
    require(receipt.get('mode') == 'FOUNDER_ONLY_USAGE_NO_PROVIDERS'
            and receipt.get('source_sql_sha256') ==
            'd20b0980c5e2d1348e7e0ecdcfa3fe021fc82b6bd1983750f37b2bf9b9ad8393',
            'existing_usage_receipt_invalid')
    inherited = REQUIREMENTS - LIVE_REQUIREMENTS - {'source_egress_and_rights_reviewed'}
    require(all(receipt.get('verified_requirements', {}).get(k) is True for k in inherited),
            'existing_usage_receipt_missing_concrete_facts')
    return evidence, dict(existing_usage_receipt=reference,
                         explicit_owner_approvals=sorted(OWNER_APPROVALS))


def preflight(evidence_path, evidence_sha):
    require(os.geteuid() == 0, 'privileged_owner_required')
    evidence, artifacts = owner_evidence(evidence_path, evidence_sha)
    files = source(evidence['head'])  # reject dirty branches before live inspection
    require(not any(p.exists() or p.is_symlink() for p in (NEW, STATE, OVERLAY)),
            'previous_or_partial_activation_present')
    require(OLD.is_dir() and OLD.stat().st_uid == 0 and not OLD.stat().st_mode & 0o022
            and not OLD.is_symlink(), 'original_release_not_frozen')
    require(sha(protected(OLD / ENTRY)) == OLD_SHA, 'original_wrapper_changed')
    gateway = service_snapshot(SERVICE)
    validate_overlay_baseline(gateway)
    crm = service_snapshot(CRM)
    baseline = dict(gateway=gateway, crm=crm, original_script_sha256=OLD_SHA)
    require(sha(encode(baseline)) == evidence['baseline_sha256'], 'live_unit_baseline_unapproved')
    before = database()
    tenant = validate_database(before)
    require(tenant['tenant_id'] == evidence['owner_tenant_id'], 'founder_identity_mismatch')
    # Prove existing active CRM owner mapping without reading protected runtime config.
    literal = quote(tenant['tenant_id'])
    actor = quote(evidence['owner_actor_id'])
    require(db("SELECT count(*) FROM public.empire_crm_tenant_memberships WHERE tenant_id::text=" +
               literal + " AND subject::text=" + actor + " AND role='owner' AND status='active' "
               "AND revoked_at IS NULL AND (valid_until IS NULL OR valid_until>now());") == '1',
            'founder_membership_unproven')
    codes = smoke(evidence['unrelated_paths'], 404)
    return dict(evidence=evidence, artifacts=artifacts, evidence_sha256=evidence_sha,
                baseline=baseline, database_before=before, http_before=codes,
                source_hashes={n: sha(b) for n, b in files.items()}), files


def quote(value):
    require(isinstance(value, str) and '\x00' not in value, 'invalid_sql_literal')
    return "'" + value.replace("'", "''") + "'"


def db_delta(before, *, undo=False):
    """One conditional tenant column update and two exact function ACL deltas.

    Entire mutation + live preimage guard in ONE transaction. No role/table/schema
    creation, API-key writes, identity changes or quota changes.
    """
    tenant = before['tenants'][0]
    after = dict(
        tenant,
        allowed_operations=tenant['allowed_operations'] + ['search'],
        monthly_cost_cap_micros=tenant['monthly_request_cap'] * tenant['search_cost_ceiling_micros'],
    )
    expected_tenant, target = (after, tenant) if undo else (tenant, after)
    operations = 'ARRAY[' + ','.join(quote(s) for s in target['allowed_operations']) + ']::text[]'
    guard = quote(json.dumps(expected_tenant)) + '::jsonb'
    acl = '\n'.join((('REVOKE EXECUTE ON FUNCTION ' if undo else 'GRANT EXECUTE ON FUNCTION ') +
                     'empire_data_cloud_api.' + name + '(' + FUNCTIONS[name] + ')' +
                     (' FROM ' if undo else ' TO ') + ROLE + ';') for name in ('reserve', 'settle'))
    expected_state = expected_database(before) if undo else before
    return """BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='30s';
SET LOCAL standard_conforming_strings=on;
LOCK TABLE empire_data_cloud_api.tenants,empire_data_cloud_api.api_keys IN SHARE ROW EXCLUSIVE MODE;
DO $owner_guard$ BEGIN
IF (""" + DB_QUERY + ')::jsonb IS DISTINCT FROM ' + quote(json.dumps(expected_state)) + """::jsonb
THEN RAISE EXCEPTION 'database_preimage_changed'; END IF;
UPDATE empire_data_cloud_api.tenants SET allowed_operations=""" + operations + """,
 monthly_cost_cap_micros=""" + str(target['monthly_cost_cap_micros']) + """
WHERE tenant_id=""" + quote(tenant['tenant_id']) + ' AND to_jsonb(tenants)=' + guard + """;
IF NOT FOUND THEN RAISE EXCEPTION 'exact_one_founder_update_required'; END IF;
END $owner_guard$;
""" + acl + '\nCOMMIT;'


def expected_database(before):
    # PostgreSQL records a superuser GRANT as made by the function owner.
    after = json.loads(json.dumps(before))
    after['tenants'][0]['allowed_operations'].append('search')
    after['tenants'][0]['monthly_cost_cap_micros'] = (
        before['tenants'][0]['monthly_request_cap']
        * before['tenants'][0]['search_cost_ceiling_micros']
    )
    # pg_catalog's aclitem OID fields serialise to strings inside to_jsonb.
    # Match their actual JSON representation when predicting exact readback.
    owner_oid = db("SELECT oid FROM pg_roles WHERE rolname='empire_data_cloud_api_owner';")
    meter_oid = db("SELECT oid FROM pg_roles WHERE rolname='" + ROLE + "';")
    for f in after['functions']:
        if f['name'] in ('reserve', 'settle'):
            f['execute'] = True
            f['acl'].append(dict(grantor=owner_oid, grantee=meter_oid,
                                 privilege_type='EXECUTE', is_grantable=False))
            f['acl'].sort(key=lambda a: (a['grantee'], a['grantor'], a['privilege_type']))
    return after


def transformed_entrypoint(raw):
    text = raw.decode()
    old = 'RELEASE = Path("' + str(OLD) + '")'
    require(text.count(old) == 1, 'entrypoint_release_anchor_changed')
    text = text.replace(old, 'RELEASE = Path("' + str(NEW) + '")')
    old_receipt = 'CONFIG.parent / "SEARCH_RELEASE_EVIDENCE.json"'
    require(text.count(old_receipt) == 1, 'entrypoint_receipt_anchor_changed')
    return text.replace(old_receipt, 'Path("' + str(RECEIPT) + '")').encode()


def overlay(pre, receipt_sha):
    # Only three additive environment assignments. Existing ExecStart, env files,
    # credentials and all other owner drop-ins remain exactly in place.
    pythonpath = str(NEW) + ':' + pre['baseline']['gateway']['pythonpath']
    require(re.fullmatch(r'[A-Za-z0-9_./:-]+', pythonpath), 'unsafe_pythonpath')
    return ('[Service]\nEnvironment="PYTHONPATH=' + pythonpath +
            '"\nEnvironment="PYTHONDONTWRITEBYTECODE=1"\nEnvironment="' +
            FLAGS[0] + '=FOUNDER_APPROVED_FIRST_PARTY_SEARCH_20261109"\nEnvironment="' +
            FLAGS[1] + '=' + receipt_sha + '"\n').encode()


def verify_tree(pre):
    for name, digest in pre['release_hashes'].items():
        require(sha(protected(NEW / name)) == digest, 'staged_source_drift')
    require(sha(protected(RECEIPT)) == pre['receipt_sha256'], 'owner_receipt_drift')


def verify_baseline(pre):
    require(service_snapshot(CRM) == pre['baseline']['crm'], 'crm_baseline_drift')
    require(service_snapshot(SERVICE) == pre['baseline']['gateway'], 'gateway_baseline_drift')
    require(sha(protected(OLD / ENTRY)) == OLD_SHA, 'original_release_drift')


def apply(evidence_path, evidence_sha):
    pre, files = preflight(evidence_path, evidence_sha)
    files[ENTRY] = transformed_entrypoint(files[ENTRY])
    pre['release_hashes'] = {n: sha(b) for n, b in files.items()}
    pre['database_after'] = expected_database(pre['database_before'])
    pre['phase'] = 'prepared'
    STATE.mkdir(mode=0o755)
    checkpoint(pre)  # durable intent before any DB/service change
    try:
        NEW.mkdir(mode=0o755)
        for name, raw in files.items():
            target = NEW / name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            write_new(target, raw)
        verify_baseline(pre)
        require(source(pre['evidence']['head']) == {**files, ENTRY: (ROOT / 'scripts' / ENTRY).read_bytes()},
                'source_changed_during_staging')
        # Persist uncertain commit state BEFORE issuing transaction; rollback
        # handles both committed and noncommitted outcomes by actual readback.
        pre['phase'] = 'db_intent'
        checkpoint(pre)
        db(db_delta(pre['database_before']))
        require(database() == pre['database_after'], 'database_delta_readback_failed')
        receipt = dict(scope='FOUNDER_ONLY_FIRST_PARTY_SEARCH_NO_PAID_API',
                       owner_actor_id=pre['evidence']['owner_actor_id'],
                       owner_tenant_id=pre['evidence']['owner_tenant_id'],
                       source_id='empire_search_fabric_public', files=pre['release_hashes'],
                       verified_requirements={k: True for k in REQUIREMENTS},
                       checked_evidence=dict(owner_sha256=evidence_sha,
                           artifacts=pre['artifacts'], baseline=pre['baseline'],
                           database_before=pre['database_before'], database_after=pre['database_after'],
                           http_before=pre['http_before'], source_hashes=pre['source_hashes']))
        # Requirement flags are compatibility output ONLY after actual checks and
        # the pinned existing receipt and explicit owner authorization; never accepted as input evidence.
        raw = encode(receipt)
        pre['receipt_sha256'] = sha(raw)
        pre['overlay_sha256'] = sha(overlay(pre, sha(raw)))
        checkpoint(pre)
        write_new(RECEIPT, raw)
        verify_tree(pre)
        verify_baseline(pre)
        smoke(pre['evidence']['unrelated_paths'], 404)
        pre['phase'] = 'overlay_intent'
        checkpoint(pre)
        write_new(OVERLAY, overlay(pre, sha(raw)))
        run(['systemctl', 'daemon-reload'])
        verify_active_overlay(pre)
        pre['phase'] = 'restart_intent'
        checkpoint(pre)
        run(['systemctl', 'restart', SERVICE])
        smoke_retry(pre, 401)
        verify_active_overlay(pre)
        verify_tree(pre)
        require(database() == pre['database_after'], 'post_smoke_database_drift')
        pre['phase'] = 'active'
        checkpoint(pre)
    except BaseException:
        try:
            rollback(pre)
        except BaseException:
            raise RuntimeError('activation_failed_rollback_incomplete') from None
        raise RuntimeError('activation_failed_rolled_back') from None


def verify_active_overlay(pre):
    current = service_snapshot(SERVICE)
    expected = pre['baseline']['gateway']
    require(current['exec'] == expected['exec'] and current['working_directory'] == expected['working_directory']
            and current['environment_files'] == expected['environment_files']
            and current['other_environment_sha256'] == expected['other_environment_sha256'], 'gateway_runtime_changed')
    require(current['dropins'] == [*expected['dropins'], str(OVERLAY)]
            and current['unit_files'] == {**expected['unit_files'], str(OVERLAY): pre['overlay_sha256']},
            'other_owner_overlay_drift')
    require(current['pythonpath'] == str(NEW) + ':' + expected['pythonpath']
            and current['bytecode_disabled'] is True
            and current['search_values'] == dict(zip(FLAGS, (
                'FOUNDER_APPROVED_FIRST_PARTY_SEARCH_20261109', pre['receipt_sha256']))),
            'effective_search_environment_changed')
    require(service_snapshot(CRM) == pre['baseline']['crm'], 'crm_owner_changed')


def smoke_retry(pre, code):
    for attempt in range(15):
        try:
            smoke(pre['evidence']['unrelated_paths'], code)
            return
        except (RuntimeError, OSError):
            if attempt == 14:
                raise
            time.sleep(1)


def rollback(pre=None):
    require(os.geteuid() == 0, 'privileged_owner_required')
    if pre is None:
        pre = json.loads(protected(JOURNAL))
    require(re.fullmatch(r'[a-f0-9]{40}', pre['evidence']['head'])
            and pre['phase'] != 'rolled_back',
            'rollback_journal_invalid')
    # Check before deleting anything; never remove another owner's replacement.
    if OVERLAY.exists() or OVERLAY.is_symlink():
        require(sha(protected(OVERLAY)) == pre.get('overlay_sha256'), 'rollback_overlay_drift')
        OVERLAY.unlink()
    # Remove our overlay/reload/restart before revoking DB privileges so no
    # search-enabled process can continue admitting requests after rollback.
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'restart', SERVICE])
    smoke_retry(pre, 404)
    verify_baseline(pre)
    actual = database()
    if actual == pre['database_after']:
        db(db_delta(pre['database_before'], undo=True))
    else:
        require(actual == pre['database_before'], 'rollback_db_drift_manual_recovery_required')
    require(database() == pre['database_before'], 'rollback_db_readback_failed')
    smoke_retry(pre, 404)
    # Only delete files this publisher staged, with exact content/path checks.
    if NEW.exists():
        require(not NEW.is_symlink(), 'rollback_release_symlink')
        for path in NEW.rglob('*'):
            require(not path.is_symlink(), 'rollback_release_symlink')
            if path.is_file():
                name = str(path.relative_to(NEW))
                require(sha(protected(path)) == pre['release_hashes'].get(name),
                        'rollback_release_drift')
        shutil.rmtree(NEW)
    if RECEIPT.exists():
        require(sha(protected(RECEIPT)) == pre['receipt_sha256'], 'rollback_receipt_drift')
        RECEIPT.unlink()
    pre['phase'] = 'rolled_back'
    checkpoint(pre)  # retain root-only nonsecret recovery evidence, prohibit rerun


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight', action='store_true')
    modes.add_argument('--apply-founder-approved', action='store_true')
    modes.add_argument('--rollback', action='store_true')
    parser.add_argument('--owner-evidence', type=Path)
    parser.add_argument('--owner-evidence-sha256')
    args = parser.parse_args()
    require(os.geteuid() == 0, 'privileged_owner_required')
    if args.preflight:
        require(args.owner_evidence is not None, 'owner_evidence_required')
        preflight(args.owner_evidence, args.owner_evidence_sha256)
    else:
        # Serialize apply and recovery; no lock file write in read-only mode.
        fd = os.open('/run/lock/empire-data-cloud-search-owner-20261109.lock',
                     os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            def interrupted(signum, frame):
                raise RuntimeError('operator_interrupted')
            signal.signal(signal.SIGTERM, interrupted)
            if args.rollback:
                rollback()
            else:
                require(args.owner_evidence is not None, 'owner_evidence_required')
                apply(args.owner_evidence, args.owner_evidence_sha256)
        finally:
            os.close(fd)
    print('OWNER_OPERATION_VERIFIED')


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        # Deliberately suppress exception text, command output and tracebacks.
        # Root-only journal preserves the last intent for explicit recovery.
        print('OWNER_OPERATION_HALTED; inspect protected journal and prerequisites', file=__import__('sys').stderr)
        raise SystemExit(1)
