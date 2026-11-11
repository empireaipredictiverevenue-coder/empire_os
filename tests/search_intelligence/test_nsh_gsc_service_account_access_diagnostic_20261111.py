"""No real Google credentials, HTTP tokens, or account changes in test suite."""
import json
from pathlib import Path
from scripts import diagnose_nsh_gsc_service_account_access_20261111 as diag


def test_config_read_single_existing_credential_reference(tmp_path):
    credential=tmp_path/'service.json'
    credential.write_text('{}')
    other=tmp_path/'basic.env'
    other.write_text('EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE='+str(credential)+'\nAPP_SECRET=not-output\n')
    assert diag._config_path((other,))==credential


def test_never_interpolate_shell_expressions(tmp_path):
    cfg=tmp_path/'config.env'
    cfg.write_text('EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE=$(curl a.sh)\n')
    try:diag._config_path((cfg,))
    except ValueError as err:assert 'unsupported_credential' in str(err)
    else:raise AssertionError('untrusted credential binding accepted')


def test_provider_missing_nsh_returns_exact_email_and_no_other_properties(monkeypatch,tmp_path):
    credential=tmp_path/'service.json'
    email='existing-empire-gsc@empire-search.iam.gserviceaccount.com'
    credential.write_text(json.dumps({'type':'service_account','client_email':email,'private_key':'SECRET_KEY_VALUE'}))
    class Credentials:
        token='SECRET_ACCESS_TOKEN'
        def refresh(self,req):pass
    class Source:
        @staticmethod
        def from_service_account_file(file,scopes):
            assert scopes==['https://www.googleapis.com/auth/webmasters.readonly']
            return Credentials()
    import sys,types
    google=types.ModuleType('google')
    auth=types.ModuleType('google.auth')
    transport=types.ModuleType('google.auth.transport')
    requests_auth=types.ModuleType('google.auth.transport.requests')
    requests_auth.Request=object
    oauth=types.ModuleType('google.oauth2')
    service=types.ModuleType('google.oauth2.service_account')
    service.Credentials=Source
    for name,module in [('google',google),('google.auth',auth),('google.auth.transport',transport),('google.auth.transport.requests',requests_auth),('google.oauth2',oauth),('google.oauth2.service_account',service)]:
        monkeypatch.setitem(sys.modules,name,module)
    class Resp:
        status_code=200
        def json(self):return {'siteEntry':[{'siteUrl':'sc-domain:empire-ai.co.uk','permissionLevel':'siteOwner'},
           {'siteUrl':'sc-domain:unrelated-secret.co.uk','permissionLevel':'siteOwner'}]}
    def fake_get(url,headers,timeout):
        assert url==diag.SITES
        assert headers['Authorization']=='Bearer SECRET_ACCESS_TOKEN'
        return Resp()
    monkeypatch.setattr(diag.requests,'get',fake_get)
    d=diag._diagnose(credential)
    assert d['status']=='NSH_NOT_GRANTED_TO_EXISTING_SERVICE_ACCOUNT'
    assert d['service_account_email']==email
    assert d['primary_permission']=='siteOwner'
    assert d['nsh_permission'] is None
    assert 'SECRET_KEY_VALUE' not in json.dumps(d)
    assert 'SECRET_ACCESS_TOKEN' not in json.dumps(d)
    assert 'unrelated-secret' not in json.dumps(d)
    assert d['permissions_modified'] is False
    assert d['token_or_key_included'] is False


def test_non_root_cannot_read_config_or_secrets(monkeypatch,capsys):
    monkeypatch.setattr(diag.os,'geteuid',lambda:1000)
    assert diag.main()==2
    x=json.loads(capsys.readouterr().out)
    assert x['status']=='ADMIN_READ_ONLY_DIAGNOSTIC_REQUIRED'
