"""Existing Ops Control sovereign host integration: passive, guarded and bounded."""
from pathlib import Path
from types import SimpleNamespace
import json

from empire_os.sovereign_infrastructure_observer import (
    collect_sovereign_infrastructure_health, UNITS,
)
from empire_os.incident_manager import build_incident_report

MEMINFO="MemTotal:       65000000 kB\nMemAvailable:   26000000 kB\n"
RAID_HEALTHY="""Personalities : [raid1]
md0 : active raid1 sda3[0] sdb2[1]
      523264 blocks super 1.2 [2/2] [UU]
md1 : active raid1 sda4[0] sdb3[1]
      971187200 blocks super 1.2 [2/2] [UU]
unused devices: <none>"""
RAID_BAD=RAID_HEALTHY.replace("[UU]","[U_]",1)
DISK=SimpleNamespace(f_blocks=900000, f_bavail=750000, f_frsize=1024)
FAILED={
    "empire-department-cycle.service":("failed","exit-code"),
    "empire-media-os.service":("failed","timeout"),
}


def runner(states):
    calls=[]
    def command(args,**kwargs):
        calls.append(args)
        assert args[0:2]==["systemctl","show"]
        assert args[2] in {name for name,_,_ in UNITS}
        assert args[3]=="--property=LoadState,ActiveState,Result"
        assert kwargs["check"] is False
        assert kwargs["timeout"]==5
        active,result=states.get(args[2],("active","success"))
        if any(name==args[2] and kind=="oneshot" for name,kind,_ in UNITS):
            if args[2] not in states:
                active,result="inactive","success"
        return SimpleNamespace(
            returncode=0,
            stdout=f"LoadState=loaded\nActiveState={active}\nResult={result}\n",
            stderr="",
        )
    return command,calls


def run(states=None,raid=RAID_HEALTHY):
    fake,calls=runner(states or FAILED)
    data=collect_sovereign_infrastructure_health(
        runner=fake,meminfo=MEMINFO,mdstat=raid,
        disk=DISK,cpu_cores=8)
    return data,calls


def test_failed_services_visible_but_no_restarts_or_egress():
    health,calls=run()
    assert health["status"]=="DEGRADED"
    assert health["infrastructure_strategy"]=="INTEGRATE_EXISTING_EMPIREOS_NO_ADDITIONAL_SERVER"
    assert health["service_findings_count"]==2
    assert {s["component"] for s in health["service_findings"]}==set(FAILED)
    assert len(calls)==len(UNITS)
    assert all(call[0:2]==["systemctl","show"] for call in calls)
    assert health["automatic_repair_actions"]==0
    assert health["new_runtime_created"] is False
    assert health["database_credentials_accessed"] is False
    assert health["secrets_reported"] is False
    assert health["payment_execution"] is False
    assert health["outbound_enabled"] is False
    assert health["database_writes"] is False
    assert health["execution_authority"]=="NONE"
    assert health["resources"]["memory_available_bytes"]==26000000*1024
    assert health["resources"]["disk_available_bytes"]==750000*1024


def test_successful_completed_oneshot_not_reported_as_failure():
    health,_=run({})
    # run({}) defaults to FAILED; explicitly fake a healthy report here.
    fakestate={name:("inactive","success") for name,kind,_ in UNITS if kind=="oneshot"}
    fake,_=runner(fakestate)
    health=collect_sovereign_infrastructure_health(
        runner=fake,meminfo=MEMINFO,mdstat=RAID_HEALTHY,disk=DISK,cpu_cores=8)
    assert health["status"]=="HEALTHY_WITH_RECOVERY_GATES"
    assert health["service_findings_count"]==0
    assert all(row["classification"]=="EXPECTED_ONESHOT"
        for row in health["observed_services"] if row["kind"]=="oneshot")
    assert len(health["recovery_evidence_blockers"])==3


def test_raid1_is_not_a_backup():
    health,_=run()
    r=health["resources"]
    assert r["raid_status"]=="MIRRORED_PRESENT"
    assert set(r["raid1_arrays"])=={"md0","md1"}
    assert r["separate_recovery_copy_verified"] is False
    assert "OFF_NODE_BACKUP_NOT_VERIFIED" in health["recovery_evidence_blockers"]
    assert "RESTORE_REHEARSAL_NOT_VERIFIED" in health["recovery_evidence_blockers"]


def test_raid_degradation_is_critical_and_not_healed():
    health,_=run(raid=RAID_BAD)
    assert health["resources"]["raid_status"]=="DEGRADED"
    assert "MIRROR_INTEGRITY_NOT_VERIFIED" in health["recovery_evidence_blockers"]
    report=build_incident_report({"findings":health["service_findings"]})
    assert report["incident_count"]>=2
    assert report["execution_authority"]=="none"
    assert health["automatic_repair_actions"]==0


def test_unknown_units_fail_observability_closed_without_action():
    def failed_command(args,**kwargs):
        return SimpleNamespace(returncode=1,stdout="",stderr="password=PRIVATE")
    data=collect_sovereign_infrastructure_health(
        runner=failed_command,meminfo="",mdstat=None,disk=None,cpu_cores=8)
    assert data["status"]=="DEGRADED"
    assert data["service_findings_count"]==len(UNITS)
    assert "PRIVATE" not in json.dumps(data)


def test_one_service_unavailable_does_not_crash_probe():
    def raises(args,**kwargs):
        if args[2]=="empire-media-os.service": raise TimeoutError("SECRET")
        return SimpleNamespace(
            returncode=0,
            stdout="LoadState=loaded\nActiveState=active\nResult=success\n",
            stderr="",
        )
    data=collect_sovereign_infrastructure_health(
        runner=raises,meminfo=MEMINFO,mdstat=RAID_HEALTHY,disk=DISK,cpu_cores=8)
    assert data["status"]=="DEGRADED"
    assert any(s["component"]=="empire-media-os.service" for s in data["service_findings"])
    assert "SECRET" not in json.dumps(data)


def test_existing_ops_control_owns_health_without_new_timer_or_server():
    script=Path("scripts/run_ops_control_cycle.py").read_text()
    observer=Path("empire_os/sovereign_infrastructure_observer.py").read_text()
    assert "collect_sovereign_infrastructure_health()" in script
    assert '"sovereign_infrastructure": sovereign_infrastructure' in script
    assert '"sovereign_infrastructure": sovereign_infrastructure["status"]' in script
    assert 'build_incident_report({' in script
    assert "execute_plan(" not in observer
    assert "systemctl start" not in observer
    assert "systemctl restart" not in observer


def test_existing_founder_ops_endpoint_reads_integrated_snapshot(tmp_path):
    from empire_os.founder_ops_api import read_ops_snapshot
    observed,_=run()
    path=tmp_path/"existing_ops_control_latest.json"
    path.write_text(json.dumps({
        "schema_version":"empire.ops_control_cycle.v1",
        "health_domains":{"sovereign_infrastructure":observed["status"]},
        "sovereign_infrastructure":observed,
        "incident_manager":build_incident_report({
            "findings":observed["service_findings"]}),
    }),encoding="utf-8")
    result=read_ops_snapshot(path)
    assert result["available"] is True
    assert result["sovereign_infrastructure"]["service_findings_count"]==2
    assert result["health_domains"]["sovereign_infrastructure"]=="DEGRADED"
    assert result["sovereign_infrastructure"]["execution_authority"]=="NONE"
