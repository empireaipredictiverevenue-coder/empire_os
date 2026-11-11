#!/usr/bin/env python3
"""One-shot guarded original Search Intelligence service activation.

Only a previously-authorised root operator may use --apply. No unit/environment
changes, no OAuth modification and no second Search Intelligence process.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path('/srv/empire_os')
UNIT = 'empire-search-intelligence-api.service'
SOURCE = ROOT / 'empire_os/search_intelligence/service.py'
NSH = ROOT / 'empire_os/search_intelligence/nsh_owned_property.py'
BASE = 'http://127.0.0.1:8771/v1/search/search-console'
ORIGINAL_SHA = '5b02db4268d26a9e704090a676afeb4e8c2a5724b16673fcde1bd58b4378afd2'
ROLLBACK_COMMIT = '1dc71f979^'
UNIT_SHA = 'a02f557c54c6f93f6a9717f9938bbca14eaf957fd2b1c1055164555d0d37bb05'
ROLLBACK_DIR = Path('/var/backups/empire-search-intelligence')

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, capture_output=True, text=True, timeout=45)

def status() -> dict[str, str]:
    p = command(['systemctl','show',UNIT,'--no-pager','-p','ActiveState','-p','MainPID','-p','FragmentPath'])
    return dict(x.split('=',1) for x in p.stdout.splitlines() if '=' in x)

def get(path: str) -> tuple[int, dict]:
    try:
        with urlopen(BASE+path,timeout=25) as response:
            return response.status, json.load(response)
    except HTTPError as e:
        return e.code, {}
    except (URLError, TimeoutError, OSError, ValueError):
        return 0, {}

def good_primary() -> bool:
    code,payload = get('/status')
    return (code==200 and payload.get('site_url')=='sc-domain:empire-ai.co.uk'
            and payload.get('available') is True)

def backup_original_bytes() -> bytes:
    p=command(['git','-C',str(ROOT),'show',f'{ROLLBACK_COMMIT}:empire_os/search_intelligence/service.py'])
    raw=p.stdout.encode()
    if b'national_storm_hub_gsc_router' in raw or b'app.include_router(router)' not in raw:
        raise RuntimeError('original_file_unexpected')
    return raw

def restore_original(original: bytes) -> dict[str,str]:
    if sha(SOURCE.read_bytes()) != ORIGINAL_SHA:
        raise RuntimeError('service_source_drift_rollback_refused')
    with tempfile.NamedTemporaryFile('wb',prefix='.search_service_recovery.',dir=SOURCE.parent,delete=False) as temp:
        temp.write(original); temp.flush(); os.fsync(temp.fileno()); tmp=Path(temp.name)
    try:
        tmp.chmod(0o644);os.replace(tmp,SOURCE)
    finally:
        tmp.unlink(missing_ok=True)
    command(['systemctl','restart',UNIT])
    for _ in range(16):
        time.sleep(1)
        if good_primary() and status().get('ActiveState')=='active':
            return status()
    raise RuntimeError('original_service_not_restored')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true',help='Run only through original authorised administrator')
    args=parser.parse_args()
    unit=Path('/etc/systemd/system')/UNIT
    if sha(SOURCE.read_bytes())!=ORIGINAL_SHA or not NSH.is_file():
        raise RuntimeError('source_drift_no_restart')
    if sha(unit.read_bytes())!=UNIT_SHA:
        raise RuntimeError('service_unit_drift_no_restart')
    before=status()
    if before.get('ActiveState')!='active' or int(before.get('MainPID','0'))<=0:
        raise RuntimeError('original_service_not_active')
    if not good_primary():
        raise RuntimeError('original_empire_search_console_unhealthy')
    new_http,new_payload=get('/national-storm-hub/status')
    if new_http==200 and new_payload.get('site_url')=='sc-domain:nationalstormhub.com':
        print(json.dumps({'state':'ALREADY_ACTIVE','original_property_preserved':True,
                          'nsh_access_available':new_payload.get('available')}));return
    if new_http!=404:
        raise RuntimeError('unknown_existing_secondary_property_state')
    print(json.dumps({'state':'SOURCE_AND_PRIMARY_PREFLIGHT_PASSED','unit':UNIT,'before_pid':before['MainPID'],
                      'new_endpoint_before':new_http,'execution_requested':args.apply,
                      'require_privileged_operator':not args.apply}))
    if not args.apply:return
    if os.geteuid()!=0:
        raise RuntimeError('requires_original_authorised_administrator')
    old=backup_original_bytes()
    ROLLBACK_DIR.mkdir(parents=True,exist_ok=True,mode=0o700)
    file=ROLLBACK_DIR/'nsh_gsc_service_original_20261111.py'
    if file.exists() and file.read_bytes()!=old:
        raise RuntimeError('existing_rollback_file_differs')
    if not file.exists():
        file.write_bytes(old); file.chmod(0o600)
    changed=False
    try:
        command(['systemctl','restart',UNIT]); changed=True
        for i in range(18):
            time.sleep(1)
            st=status()
            if st.get('ActiveState')!='active' or not good_primary():continue
            new_http,new_payload=get('/national-storm-hub/status')
            if new_http==200 and new_payload.get('site_url')=='sc-domain:nationalstormhub.com':
                result={'state':'LIVE_SECOND_PROPERTY_ROUTE_VERIFIED','service_pid':st['MainPID'],
                        'original_property_preserved':True,'second_property':'sc-domain:nationalstormhub.com',
                        'nsh_access_available':new_payload.get('available') is True,
                        'permission_or_provider_unavailable':new_payload.get('available') is False,
                        'rollback_file':str(file)}
                print(json.dumps(result,sort_keys=True));return
        raise RuntimeError('post_restart_primary_or_secondary_verification_failed')
    except Exception as error:
        if changed:
            recovered=restore_original(old)
            print(json.dumps({'state':'ROLLED_BACK_TO_PREVIOUS_OWNER_READER','original_property_preserved':True,
                              'recovered_pid':recovered.get('MainPID'),'failure_class':type(error).__name__}),file=sys.stderr)
        raise

if __name__=='__main__':
    try:main()
    except Exception as ex:
        print(json.dumps({'state':'HELD','reason_class':type(ex).__name__,'reason':str(ex)[:180]}),file=sys.stderr)
        sys.exit(2)
