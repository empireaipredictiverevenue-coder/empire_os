"""Read-only Founder inbox release gates."""
import json
import pytest
from scripts import deploy_founder_canonical_reply_view as release


def test_default_is_noop(capsys):
    assert release.main([]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'REVIEW_ONLY'
    assert result['mail_sent'] is False
    assert result['database_writes'] is False


def test_apply_requires_explicit_approval(capsys):
    assert release.main(['--apply']) == 2
    assert json.loads(capsys.readouterr().out)['reason'] == 'EXPLICIT_BOUNDED_RELEASE_REQUIRED'


def test_nonroot_held(monkeypatch, capsys):
    monkeypatch.setattr(release.os, 'geteuid', lambda: 1000)
    assert release.main(['--apply', '--approved-canonical-reply-view-only']) == 2
    assert json.loads(capsys.readouterr().out)['reason'] == 'ROOT_ACCESS_REQUIRED'

def simulated_release(monkeypatch, tmp_path):
    secret_path = tmp_path / 'secure' / 'reader.dsn'
    dropin = tmp_path / 'unit' / 'reader.conf'
    monkeypatch.setattr(release, 'PRIVATE_DSN_FILE', secret_path)
    monkeypatch.setattr(release, 'SYSTEMD_DROPIN', dropin)
    monkeypatch.setattr(release, '_protected_dsn', lambda: 'fixture-reader')
    preflights = []
    monkeypatch.setattr(release, '_preflight_role', lambda s: preflights.append(s))
    commands = []
    monkeypatch.setattr(release, '_systemctl', lambda c: commands.append(c))
    def response(url):
        if url == release.READINESS_URL:
            return {'provider':'empiredb_canonical_replies', 'configured':True,
                    'execution_authority':'none', 'read_only': True}
        return {'provider':'empiredb_canonical_replies', 'read_only':True,
                'execution_authority':'none', 'suppression_evidence_complete':False}
    monkeypatch.setattr(release, '_json_probe', response)
    return secret_path, dropin, preflights, commands


def test_bounded_release_success(monkeypatch, tmp_path):
    secret, dropin, preflights, commands = simulated_release(monkeypatch, tmp_path)
    report = release.activate()
    assert report['status'] == 'CANONICAL_REPLY_VIEW_ACTIVE'
    assert preflights == ['fixture-reader']
    assert secret.stat().st_mode & 0o777 == 0o600
    assert dropin.stat().st_mode & 0o777 == 0o644
    assert 'LoadCredential=' in dropin.read_text()
    assert commands == ['daemon-reload', 'restart']
    assert report['send_authorized'] is False


def test_failed_live_readback_rolls_back(monkeypatch, tmp_path):
    secret, dropin, _, commands = simulated_release(monkeypatch, tmp_path)
    monkeypatch.setattr(release, '_json_probe', lambda url: {'provider':'owned_imap'})
    with pytest.raises(release.ReleaseHeld, match='CANONICAL_REPLY_RELEASE_ROLLED_BACK'):
        release.activate()
    assert not secret.exists()
    assert not dropin.exists()
    assert commands == ['daemon-reload', 'restart', 'daemon-reload', 'restart']

def test_role_preflight_rejects_privileged_login(monkeypatch):
    import psycopg
    calls = []
    class Cur:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, sql, params=None): calls.append(sql)
        def fetchone(self): return (True, False, False, False, False)
    class Con:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def cursor(self): return Cur()
    monkeypatch.setattr(psycopg, 'connect', lambda *a,**kw: Con())
    with pytest.raises(release.ReleaseHeld, match='ELEVATED_ROLE_ATTRIBUTES'):
        release._preflight_role('fixture-dsn')
    assert all('INSERT INTO' not in x for x in calls)


def test_role_preflight_rejects_write_privileges(monkeypatch):
    import psycopg
    replies = iter([(False, False, False, False, False), (True, False, False)])
    class Cur:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, sql, params=None): pass
        def fetchone(self): return next(replies)
    class Con:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def cursor(self): return Cur()
    monkeypatch.setattr(psycopg, 'connect', lambda *a,**kw: Con())
    with pytest.raises(release.ReleaseHeld, match='READER_LOGIN_NOT_STRICTLY_READ_ONLY'):
        release._preflight_role('fixture-dsn')

def test_uvicorn_startup_delay_does_not_trigger_false_rollback(monkeypatch, tmp_path):
    secret, dropin, _, commands = simulated_release(monkeypatch, tmp_path)
    checks = []
    def delayed_probe(url):
        checks.append(url)
        if url == release.READINESS_URL and checks.count(release.READINESS_URL) < 4:
            raise release.ReleaseHeld("FOUNDER_READ_ENDPOINT_UNAVAILABLE")
        if url == release.READINESS_URL:
            return {
                "provider": "empiredb_canonical_replies", "configured": True,
                "execution_authority": "none", "read_only": True,
            }
        return {
            "provider": "empiredb_canonical_replies", "read_only": True,
            "execution_authority": "none", "suppression_evidence_complete": False,
        }
    monkeypatch.setattr(release, "_json_probe", delayed_probe)
    monkeypatch.setattr(release.time, "sleep", lambda seconds: None)
    result = release.activate()
    assert result["status"] == "CANONICAL_REPLY_VIEW_ACTIVE"
    assert checks.count(release.READINESS_URL) == 4
    assert checks[-1] == release.SUMMARY_URL
    assert commands == ["daemon-reload", "restart"]
    assert secret.is_file() and dropin.is_file()


def test_summary_transient_unavailable_is_retried_not_treated_as_broken(monkeypatch, tmp_path):
    secret, dropin, _, commands = simulated_release(monkeypatch, tmp_path)
    counts = {"summary": 0}
    def delayed_summary(url):
        if url == release.SUMMARY_URL:
            counts["summary"] += 1
            if counts["summary"] < 3:
                raise release.ReleaseHeld("FOUNDER_READ_ENDPOINT_NON_200")
            return {
                "provider": "empiredb_canonical_replies", "read_only": True,
                "execution_authority": "none", "suppression_evidence_complete": False,
            }
        return {
            "provider": "empiredb_canonical_replies", "configured": True,
            "execution_authority": "none", "read_only": True,
        }
    monkeypatch.setattr(release, "_json_probe", delayed_summary)
    monkeypatch.setattr(release.time, "sleep", lambda seconds: None)
    report = release.activate()
    assert report["status"] == "CANONICAL_REPLY_VIEW_ACTIVE"
    assert counts["summary"] == 3
    assert commands == ["daemon-reload", "restart"]


def test_real_contract_mismatch_never_becomes_success_after_wait(monkeypatch, tmp_path):
    secret, dropin, _, commands = simulated_release(monkeypatch, tmp_path)
    monkeypatch.setattr(release, "_json_probe", lambda url: {
        "provider": "empiredb_canonical_replies", "configured": False,
        "execution_authority": "none", "read_only": True,
    })
    with pytest.raises(
        release.ReleaseHeld,
        match="CANONICAL_REPLY_RELEASE_ROLLED_BACK:LIVE_CANONICAL_READINESS_CONTRACT_UNVERIFIED",
    ):
        release.activate()
    assert not secret.exists() and not dropin.exists()
    assert commands == ["daemon-reload", "restart", "daemon-reload", "restart"]


def test_startup_timeout_still_rolls_back_and_identifies_stage(monkeypatch, tmp_path):
    secret, dropin, _, commands = simulated_release(monkeypatch, tmp_path)
    monkeypatch.setattr(
        release, "_json_probe",
        lambda url: (_ for _ in ()).throw(release.ReleaseHeld("FOUNDER_READ_ENDPOINT_UNAVAILABLE"))
    )
    times = iter([0.0, 15.0])
    monkeypatch.setattr(release.time, "monotonic", lambda: next(times))
    with pytest.raises(
        release.ReleaseHeld,
        match="CANONICAL_REPLY_RELEASE_ROLLED_BACK:FOUNDER_SERVICE_STARTUP_TIMEOUT_READINESS",
    ):
        release.activate()
    assert not secret.exists() and not dropin.exists()
    assert commands == ["daemon-reload", "restart", "daemon-reload", "restart"]


def test_summary_contract_failure_cannot_become_success(monkeypatch, tmp_path):
    secret, dropin, _, commands = simulated_release(monkeypatch, tmp_path)
    monkeypatch.setattr(release, "_json_probe", lambda url: ({
        "provider": "empiredb_canonical_replies", "configured": True,
        "read_only": True, "execution_authority": "none",
    } if url == release.READINESS_URL else {
        "provider": "empiredb_canonical_replies",
        "read_only": True, "execution_authority": "write",
        "suppression_evidence_complete": True,
    }))
    with pytest.raises(
        release.ReleaseHeld,
        match="CANONICAL_REPLY_RELEASE_ROLLED_BACK:LIVE_CANONICAL_SUMMARY_CONTRACT_UNVERIFIED",
    ):
        release.activate()
    assert not secret.exists() and not dropin.exists()
