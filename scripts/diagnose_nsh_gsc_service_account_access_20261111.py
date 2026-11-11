#!/usr/bin/env python3
"""Read-only GSC access diagnosis for the ORIGINAL Empire Search service account.

The operator runs under normal admin controls, because the credential JSON is
protected. Never display OAuth tokens, private keys, configuration values,
third-party property identities or raw Google API error responses.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests

CONNECTION_FILES=(
    Path('/etc/empire_os.env'),
    Path('/etc/empire_search_intelligence.env'),
    Path('/etc/empire-seo-inventory-20261104.env'),
)
FIELD='EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE'
SITES='https://searchconsole.googleapis.com/webmasters/v3/sites'
TARGET='sc-domain:nationalstormhub.com'
PRIMARY='sc-domain:empire-ai.co.uk'
ACCEPTED={'siteOwner','siteFullUser','siteRestrictedUser'}


def _config_path(paths:tuple[Path,...]=CONNECTION_FILES)->Path:
    """Find only the exact active credential-file reference, not raw contents."""
    value=None
    pattern=re.compile(r'^(?:export\s+)?EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE\s*=\s*(.+)$')
    for path in paths:
        if not path.is_file():
            if path.name=='empire_search_intelligence.env':
                raise ValueError('existing_search_intelligence_env_unavailable')
            continue
        for line in path.read_text(encoding='utf8').splitlines():
            match=pattern.fullmatch(line.strip())
            if match:
                raw=match.group(1).strip()
                if len(raw)>=2 and raw[0] in ('"',"'") and raw[-1]==raw[0]:
                    raw=raw[1:-1]
                if not raw.startswith('/') or any(c in raw for c in ('$', '`','\n','\r')):
                    raise ValueError('unsupported_credential_file_binding')
                value=Path(raw)
    if value is None or not value.is_file():
        raise ValueError('existing_gsc_credential_file_unavailable')
    return value


def _diagnose(path:Path)->dict[str,Any]:
    try:
        data=json.loads(path.read_text())
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError('service_account_credential_unreadable') from exc
    if not isinstance(data,dict) or data.get('type')!='service_account':
        raise ValueError('existing_gsc_credentials_not_service_account')
    email=data.get('client_email')
    if not isinstance(email,str) or not email.endswith('.gserviceaccount.com') or len(email)>240:
        raise ValueError('invalid_service_account_identity')
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
        creds=service_account.Credentials.from_service_account_file(
            str(path),scopes=['https://www.googleapis.com/auth/webmasters.readonly'])
        creds.refresh(Request())
    except Exception as exc:
        raise ValueError('read_only_gsc_token_refresh_failed') from exc
    token=creds.token
    if not token:
        raise ValueError('token_refresh_unavailable')
    try:
        response=requests.get(SITES,headers={
            'Authorization':'Bearer '+token,'Accept':'application/json'},timeout=20)
    except requests.RequestException as exc:
        raise ValueError('gsc_sites_list_network_failed') from exc
    result={
        'schema':'empire.search_intelligence.gsc_service_account_access_diagnostic.v1',
        'mode':'READ_ONLY','service_account_email':email,
        'primary_property':PRIMARY,'target_property':TARGET,
        'provider_http_status':response.status_code,
        'token_or_key_included':False,'other_property_names_included':False,
        'source':'official_google_gsc_sites_list',
        'permissions_modified':False,'existing_search_service_modified':False,
    }
    if response.status_code !=200:
        result.update({'status':'GOOGLE_SITES_LIST_REQUEST_REJECTED',
                       'reason':'review_account_or_api_permissions',
                       'primary_permission':None,'nsh_permission':None})
        return result
    try:
        payload=response.json()
    except ValueError as exc:
        raise ValueError('provider_response_not_json') from exc
    rows=payload.get('siteEntry',[]) if isinstance(payload,dict) else None
    if not isinstance(rows,list) or len(rows)>2000:
        raise ValueError('invalid_provider_sites_list')
    by_exact={}
    for row in rows:
        if not isinstance(row,dict):raise ValueError('invalid_property_entry')
        name=row.get('siteUrl')
        if name in (PRIMARY,TARGET,'https://nationalstormhub.com/'):
            if name in by_exact:raise ValueError('duplicate_owned_property_entries')
            by_exact[name]=row.get('permissionLevel')
    got=by_exact.get(TARGET)
    result.update({
        'status':'NSH_ACCESS_VERIFIED' if got in ACCEPTED else 'NSH_NOT_GRANTED_TO_EXISTING_SERVICE_ACCOUNT',
        'primary_permission':by_exact.get(PRIMARY),
        'nsh_permission':got,
        'nsh_url_prefix_permission':by_exact.get('https://nationalstormhub.com/'),
        'nsh_access_verified':got in ACCEPTED,
        'properties_listed_count':len(rows),
    })
    return result


def main()->int:
    if os.geteuid()!=0:
        print(json.dumps({'status':'ADMIN_READ_ONLY_DIAGNOSTIC_REQUIRED','no_changes':True}))
        return 2
    try:
        result=_diagnose(_config_path())
    except (OSError,ValueError,TypeError) as exc:
        result={'status':'DIAGNOSTIC_UNAVAILABLE','reason':str(exc)[:90],
                'secrets_exposed':False,'permissions_modified':False}
    print(json.dumps(result,sort_keys=True))
    return 0 if result.get('status') in ('NSH_ACCESS_VERIFIED','NSH_NOT_GRANTED_TO_EXISTING_SERVICE_ACCOUNT') else 2

if __name__=='__main__':
    raise SystemExit(main())
