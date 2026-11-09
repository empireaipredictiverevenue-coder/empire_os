"""Read-only PostgreSQL local auth and 066 source gate preflight."""
import json,subprocess
SQL="""
SELECT current_setting('port'),current_setting('password_encryption'),
 (SELECT count(*) FROM pg_catalog.pg_hba_file_rules
    WHERE type='host' AND error IS NULL
      AND auth_method IN ('scram-sha-256','md5')
      AND address IN ('127.0.0.1','::1')),
 (SELECT count(*) FROM pg_catalog.pg_roles
    WHERE rolname='empire_predictive_rights_login'),
 (SELECT count(*) FROM public.empire_predictive_source_rights_candidate_held);
"""
p=subprocess.run(["sudo","-n","runuser","-u","postgres","--","psql",
                  "-XAt","-w","-v","ON_ERROR_STOP=1","-d","empiredb","-c",SQL],
                 capture_output=True,text=True,timeout=10)
if p.returncode: print(json.dumps({"status":"NO_PG_HBA_PROOF","no_changes":True}))
else:
 r=p.stdout.strip().split("|")
 if len(r)!=5:raise RuntimeError("unexpected_preflight")
 print(json.dumps(dict(port=int(r[0]),password_encryption=r[1],
           loopback_scram_rules=int(r[2]),login_present=int(r[3])==1,
           rights_rows=int(r[4]),no_changes=True),sort_keys=True))
