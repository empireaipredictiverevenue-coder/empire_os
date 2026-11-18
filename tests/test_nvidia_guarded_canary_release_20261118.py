"""Guarded NVIDIA two-tenant synthetic release acceptance and mock Docker.

Exercises both live no-write preflight and the post-launch inspector against
a fully injected Docker API. No Docker daemon access, container launch,
identity signing, external model use or customer dataset in this suite.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import release_nvidia_two_tenant_private_canary_20261118 as release
from scripts import verify_nvidia_two_tenant_running_20261118 as reader


def test_live_readonly_release_preflight():
    report=release.preflight(require_resource_headroom=False)
    assert report["original_health_preserved"] is True
    assert report["original_mcp_pid"]>0
    assert report["two_private_tenant_sources_pinned"] is True
    assert report["tenant_ports_available"] is True
    assert report["required_memory_gib"]==24
    assert isinstance(report["available_host_memory_preflight"],bool)
    assert report["customer_data_admission"] is False
    assert not release.RECEIPT.exists()


def test_unguarded_caller_cannot_apply_docker_deployment():
    if release.os.geteuid()==0:
        pytest.skip("root-only denial tested by actual unprivileged environment")
    with pytest.raises(PermissionError):
        release.activate()
    assert not release.RECEIPT.exists()


def test_explicit_release_only_touches_two_isolated_projects():
    for label,*_ in release.TENANTS:
        cmd=release.compose(label,"up","-d","--no-build","--pull","never")
        assert cmd[0]=="/usr/bin/docker"
        assert cmd[1]=="compose"
        assert cmd[2]=="--project-name"
        assert cmd[3]==f"nvidia-tenant-{label}-20261118"
        assert str(release.STAGE/f"tenant_{label}"/"tenant.env") in cmd
        assert str(release.STAGE/f"tenant_{label}"/"compose.yaml") in cmd
        assert "--no-build" in cmd
        assert "--pull" in cmd
        assert "never" in cmd
    assert "empire-nvidia-ontology-eval:3825917" in release.CACHED_IMAGES
    assert "empire-nvidia-ontology-frontend-eval:3825917" in release.CACHED_IMAGES


def test_failed_release_rollback_touches_only_candidate_projects(monkeypatch):
    calls=[]
    monkeypatch.setattr(release,"call",lambda *args,**kw:calls.append(args))
    release.rollback_only_new(["a","b"])
    assert len(calls)==2
    assert [args[3] for args in calls]==[
        "nvidia-tenant-b-20261118",
        "nvidia-tenant-a-20261118",
    ]
    assert all(args[-1]=="down" for args in calls)
    assert all("empire-nvidia-ontology-eval" not in args for args in calls)
    assert all("--volumes" not in args for args in calls)


def fake_docker(changes=None):
    changes=changes or {}
    def call(*args):
        if args[0]=="compose":
            project=args[2]
            service=args[-1]
            return f"{project}-{service}-container"
        if args[0]=="inspect":
            payload=args[2]
            container=args[3]
            label="a" if "-tenant-a-" in container else "b"
            project=f"nvidia-tenant-{label}-20261118"
            if payload=="{{.HostConfig.Memory}}":
                service=container[len(project)+1:-len("-container")]
                cap=int(reader.LIMITS[service][:-1])*1024**3
                if changes.get("memory_cap_bypassed") and label=="a" and service=="auto-ontology":
                    cap+=1
                return str(cap)
            if payload=="{{json .Config.Labels}}":
                return json.dumps({
                    "com.docker.compose.project":(
                        "unauthorized-project" if changes.get("label_mismatch") and label=="a"
                        else project)
                })
            if payload=="{{json .Mounts}}":
                if "-postgres-container" in container:
                    return json.dumps([{
                        "Name":project+"_postgres_data",
                        "Destination":"/var/lib/postgresql/data",
                        "Type":"volume"
                    }])
                return json.dumps([{
                    "Type":"bind",
                    "Source":str(reader.STAGE/f"tenant_{label}"/f"source_{label}.sqlite"),
                    "Destination":"/reference/empire_graph.sqlite",
                    "RW":bool(changes.get("source_writable") and label=="a"),
                }])
            if payload=="{{json .NetworkSettings.Networks}}":
                name=project+"_sandbox"
                if changes.get("shared_network") and label=="b":
                    name="nvidia-tenant-a-20261118_sandbox"
                return json.dumps({name:{}})
            if payload=="{{json .NetworkSettings.Ports}}":
                port=33100 if label=="a" else 33101
                host="0.0.0.0" if changes.get("public_frontend") and label=="a" else "127.0.0.1"
                return json.dumps({"3000/tcp":[{
                    "HostIp":host,"HostPort":str(port)
                }]})
        if args[0]=="exec":
            container=args[1]
            label="a" if "-tenant-a-" in container else "b"
            count=2 if label=="a" else 7
            if changes.get("foreign_sql_rows") and label=="b":
                return json.dumps([["a",2],["b",7]])
            return json.dumps([[label,count]])
        raise AssertionError("unexpected fake Docker read command")
    return call


def test_two_dedicated_docker_runtime_inspections_pass_without_daemon(monkeypatch):
    monkeypatch.setattr(reader.os,"geteuid",lambda:0)
    monkeypatch.setattr(reader,"docker",fake_docker())
    result=reader.inspect_live()
    assert result["status"]=="TWO_NVIDIA_SYNTHETIC_CONTAINER_SQL_SOURCES_ISOLATED"
    assert result["no_cross_tenant_mounted_rows"] is True
    assert result["projects"]["a"]["actual_container_sql_rows"]==2
    assert result["projects"]["b"]["actual_container_sql_rows"]==7
    assert result["production_tenant_sql_approved"] is False
    assert result["semantic_nlp_cross_tenant_verified"] is False


@pytest.mark.parametrize("case",[
    "label_mismatch","source_writable","shared_network",
    "public_frontend","foreign_sql_rows","memory_cap_bypassed"
])
def test_every_unsafe_docker_runtime_drift_is_hard_denial(monkeypatch,case):
    monkeypatch.setattr(reader.os,"geteuid",lambda:0)
    monkeypatch.setattr(reader,"docker",fake_docker({case:True}))
    with pytest.raises(RuntimeError):
        reader.inspect_live()


def test_deployment_never_launches_or_signs_during_readonly_mode(monkeypatch):
    calls=[]
    monkeypatch.setattr(release,"call",lambda *args,**kwargs:calls.append(args))
    outcome=release.preflight(require_resource_headroom=False)
    assert outcome["customer_data_admission"] is False
    assert calls
    assert all("up" not in command and "down" not in command
               for command in calls)
    assert not release.RECEIPT.exists()


def test_cannot_start_full_two_stack_canary_without_safe_memory_headroom(monkeypatch):
    monkeypatch.setattr(release,"required_memory_budget",lambda:1<<80)
    with pytest.raises(RuntimeError,match="insufficient available memory"):
        release.preflight()
    assert not release.RECEIPT.exists()
