"""Read-only review of actual empiredb_migrator role membership (no secrets)."""
import json
import subprocess
SQL = """
SELECT r.rolname,r.rolcanlogin,r.rolsuper,
       m.admin_option,m.inherit_option,m.set_option
FROM pg_catalog.pg_auth_members AS m
JOIN pg_catalog.pg_roles AS r ON r.oid=m.member
WHERE m.roleid=(SELECT oid FROM pg_catalog.pg_roles
                WHERE rolname='empiredb_migrator')
ORDER BY r.rolname;
"""
p=subprocess.run(["sudo","-n","runuser","-u","postgres","--","psql",
                  "-XAt","-w","-v","ON_ERROR_STOP=1","-d","empiredb","-c",SQL],
                 capture_output=True,text=True,timeout=10)
if p.returncode:
 print(json.dumps({"result":"read_only_unavailable","changes":False}))
else:
 result=[]
 for row in p.stdout.splitlines():
  parts=row.strip().split("|")
  if len(parts)!=6:raise RuntimeError("membership_catalog_changed")
  result.append(dict(role=parts[0],login=parts[1]=="t",superuser=parts[2]=="t",
                     admin=parts[3]=="t",inherit=parts[4]=="t",set_role=parts[5]=="t"))
 print(json.dumps({"member_count":len(result),"members":result,"changes":False},sort_keys=True))
