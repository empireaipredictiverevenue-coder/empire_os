"""Unit/credential distinction tested with synthetic systemd and /proc."""
import pytest

from empire_os.agent_runtime_identity_evidence import (
    MANAGED_WORKERS, ExistingWorkerBinding, inspect_existing_worker,
    inspect_agent_team, proc_identity, systemd_show,
)


CODER = MANAGED_WORKERS[0]


def simulated(*, unit=None, active="active", substate="running",
              pid="2121", user="ubuntu", uid=1000, cgroup=None):
    unit = CODER.unit if unit is None else unit
    cgroup = cgroup if cgroup is not None else f"/system.slice/{CODER.unit}"
    return inspect_existing_worker(
        CODER,
        show=lambda _: {
            "Id": unit, "ActiveState": active, "SubState": substate,
            "MainPID": pid, "User": user,
        },
        proc=lambda _: (uid, cgroup),
        get_uid=lambda _: 1000,
    )


def test_exact_original_unit_pid_uid_and_cgroup_observed_but_not_authenticated():
    row = simulated()
    assert row["managed_process_evidence"] is True
    assert row["unit_active"] is True
    assert row["main_pid_observed"] is True
    assert row["process_uid_verified"] is True
    assert row["process_unit_cgroup_verified"] is True
    assert row["dedicated_agent_key_verified"] is False
    assert row["authenticated_collaboration_activated"] is False
    assert row["execution_authority"] == "none"


@pytest.mark.parametrize("options", [
    {"active": "inactive"},
    {"active": "activating"},
    {"pid": "0"},
    {"pid": "not_a_pid"},
    {"pid": "-1"},
    {"uid": 0},
    {"user": "root"},
    {"unit": "empire-another-worker.service"},
    {"cgroup": "/system.slice/empire-another-worker.service"},
    {"cgroup": "/system.slice/empire-coder-worker.service-fake"},
    {"cgroup": ""},
])
def test_fail_closed_when_any_process_fact_is_missing_or_false(options):
    row = simulated(**options)
    assert row["managed_process_evidence"] is False
    assert row["dedicated_agent_key_verified"] is False


def test_unregistered_agent_or_changed_authority_cannot_invent_worker():
    different = ExistingWorkerBinding(
        agent_id="empire_coder", unit=CODER.unit,
        department="engineering", role="coder",
        component="ops_sentinel",
    )
    with pytest.raises(ValueError, match="unregistered"):
        inspect_existing_worker(different)
    fake = ExistingWorkerBinding(
        agent_id="new_buyer_agent",
        unit="new-buyer.service",
        department="sales_revenue",
        role="sales",
        component="identity_enrichment",
    )
    with pytest.raises(ValueError, match="unregistered"):
        inspect_existing_worker(fake)


def test_zero_service_show_does_not_invent_pid_or_agent():
    row = inspect_existing_worker(
        CODER,
        show=lambda _: {},
        proc=lambda _: (_ for _ in ()).throw(AssertionError("proc must not be read")),
    )
    assert row["main_pid_observed"] is False
    assert row["managed_process_evidence"] is False


def test_invalid_readback_unit_id_is_ignored_even_if_pid_valid():
    row = simulated(unit="fake.service")
    assert row["managed_process_evidence"] is False


def test_proc_identity_reads_only_status_and_cgroup(tmp_path):
    folder = tmp_path / "77"
    folder.mkdir()
    (folder / "status").write_text("Name:\tpython\nUid:\t1000\t1000\t1000\t1000\n")
    (folder / "cgroup").write_text("0::/system.slice/empire-coder-worker.service\n")
    (folder / "environ").write_text("CRITICAL_SECRET=do_not_read\n")
    assert proc_identity(77, tmp_path) == (
        1000, "/system.slice/empire-coder-worker.service",
    )
    assert proc_identity(78, tmp_path) == (None, "")


def test_service_readonly_only_allowlisted_units():
    assert systemd_show("systemd-journald.service") == {}


def test_inventory_does_not_exaggerate_auth(monkeypatch):
    import empire_os.agent_runtime_identity_evidence as mod
    monkeypatch.setattr(mod, "inspect_existing_worker", lambda binding: {
        "agent_id": binding.agent_id,
        "managed_process_evidence": True,
        "dedicated_agent_key_verified": False,
    })
    row = inspect_agent_team()
    assert row["managed_process_evidence_count"] == len(MANAGED_WORKERS)
    assert row["authenticated_agent_count"] == 0
    assert row["communication_activated"] is False
    assert "model_provider" in row["other_runtime_holds"]["jev"]


def test_actual_main_process_and_pinned_role_preflight_with_injected_key():
    from empire_os.agent_runtime_identity_evidence import preflight_local_managed_binding
    from empire_os.department_collaboration import AgentCredential, existing_role_profile
    credential = AgentCredential(
        existing_role_profile(
            agent_id="empire_coder", department="engineering", role="coder",
            capabilities=("empire_coder",),
        ), b"K" * 32,
    )
    observed = preflight_local_managed_binding(
        credential, agent_id="empire_coder", process_pid=2121,
        show=lambda _: {
            "Id": CODER.unit, "ActiveState": "active",
            "SubState": "running", "MainPID": "2121", "User": "ubuntu",
        },
        proc=lambda _: (1000, f"/system.slice/{CODER.unit}"),
        get_uid=lambda _: 1000,
    )
    assert observed["local_process_scope_attested"] is True
    assert observed["trusted_broker_key_registration_still_required"] is True
    assert observed["execution_authority"] == "none"


@pytest.mark.parametrize("variation", [
    {"process_pid": 2122}, {"process_pid": 0},
    {"cgroup": "/system.slice/another.service"},
    {"active": "inactive"},
    {"uid": 999},
])
def test_other_process_cannot_claim_a_managed_agent_identity(variation):
    from empire_os.agent_runtime_identity_evidence import preflight_local_managed_binding
    from empire_os.department_collaboration import AgentCredential, existing_role_profile
    credential = AgentCredential(existing_role_profile(
        agent_id="empire_coder", department="engineering", role="coder",
        capabilities=("empire_coder",),
    ), b"K" * 32)
    unit = CODER.unit
    with pytest.raises(ValueError, match="not_attested"):
        preflight_local_managed_binding(
            credential, agent_id="empire_coder",
            process_pid=variation.get("process_pid", 2121),
            show=lambda _: {
                "Id": unit, "ActiveState": variation.get("active", "active"),
                "SubState": "running", "MainPID": "2121", "User": "ubuntu",
            },
            proc=lambda _: (variation.get("uid", 1000),
                            variation.get("cgroup", f"/system.slice/{unit}")),
            get_uid=lambda _: 1000,
        )


def test_wrong_managed_role_or_capability_cannot_register():
    from empire_os.agent_runtime_identity_evidence import preflight_local_managed_binding
    from empire_os.department_collaboration import AgentCredential, existing_role_profile
    bad = AgentCredential(existing_role_profile(
        agent_id="empire_coder", department="sales_revenue", role="sales",
        capabilities=("identity_enrichment",),
    ), b"K" * 32)
    with pytest.raises(ValueError, match="scope_mismatch"):
        preflight_local_managed_binding(bad, agent_id="empire_coder")


def test_unpinned_provider_name_cannot_become_an_agent():
    from empire_os.agent_runtime_identity_evidence import preflight_local_managed_binding
    with pytest.raises(ValueError, match="not_registered"):
        preflight_local_managed_binding(object(), agent_id="jev")


def test_readiness_process_inspection_is_explicit_opt_in(tmp_path, monkeypatch):
    import empire_os.agent_runtime_identity_evidence as mod
    from empire_os.agent_collaboration_readiness import review_existing_agent_collaboration
    monkeypatch.setattr(mod, "inspect_agent_team", lambda: {
        "authenticated_agent_count": 0,
        "managed_process_evidence_count": 1,
    })
    original = review_existing_agent_collaboration(tmp_path)
    assert "managed_runtime_identity_evidence" not in original
    selected = review_existing_agent_collaboration(
        tmp_path, include_managed_runtime_identity=True,
    )
    assert selected["managed_runtime_identity_evidence"]["managed_process_evidence_count"] == 1
    assert selected["trusted_agent_credentials_verified"] is False


@pytest.mark.parametrize("phase,expected", [
    (("activating", "start"), True),
    (("activating", "start-post"), False),
    (("activating", "start-pre"), False),
    (("activating", "auto-restart"), False),
    (("active", "running"), True),
    (("active", "exited"), False),
    (("failed", "failed"), False),
    (("inactive", "dead"), False),
])
def test_actual_oneshot_main_process_phase_not_just_active_status(phase, expected):
    state, substate = phase
    observed = inspect_existing_worker(
        CODER,
        show=lambda _: {
            "Id": CODER.unit, "ActiveState": state,
            "SubState": substate, "MainPID": "5501", "User": "ubuntu",
        },
        proc=lambda _: (1000, f"/system.slice/{CODER.unit}"),
        get_uid=lambda _: 1000,
    )
    assert observed["managed_process_evidence"] is expected
    assert observed["oneshot_execstart_observed"] is (
        expected and state == "activating"
    )


def test_oneshot_actual_main_process_can_pass_attested_signer_check():
    from empire_os.agent_runtime_identity_evidence import (
        ManagedWorkerSigningIdentity, preflight_local_managed_binding,
    )
    from empire_os.department_collaboration import existing_role_profile
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    profile = existing_role_profile(
        agent_id="empire_coder", department="engineering", role="coder",
        capabilities=("empire_coder",),
    )
    signed_identity = ManagedWorkerSigningIdentity(
        profile, Ed25519PrivateKey.generate(),
    )
    result = preflight_local_managed_binding(
        signed_identity,
        agent_id="empire_coder",
        process_pid=5501,
        show=lambda _: {
            "Id": CODER.unit, "ActiveState": "activating",
            "SubState": "start", "MainPID": "5501", "User": "ubuntu",
        },
        proc=lambda _: (1000, f"/system.slice/{CODER.unit}"),
        get_uid=lambda _: 1000,
    )
    assert result["local_process_scope_attested"] is True
    assert result["signing_mode"] == "ed25519_private_in_managed_process"
    assert result["trusted_broker_key_registration_still_required"] is True


@pytest.mark.parametrize("substate", ["start-pre", "start-post", "auto-restart"])
def test_oneshot_phase_other_than_execstart_is_not_signing_authority(substate):
    from empire_os.agent_runtime_identity_evidence import (
        ManagedWorkerSigningIdentity, preflight_local_managed_binding,
    )
    from empire_os.department_collaboration import existing_role_profile
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    profile = existing_role_profile(
        agent_id="empire_coder", department="engineering", role="coder",
        capabilities=("empire_coder",),
    )
    identity = ManagedWorkerSigningIdentity(profile, Ed25519PrivateKey.generate())
    with pytest.raises(ValueError, match="not_attested"):
        preflight_local_managed_binding(
            identity, agent_id="empire_coder", process_pid=5501,
            show=lambda _: {
                "Id": CODER.unit, "ActiveState": "activating",
                "SubState": substate, "MainPID": "5501", "User": "ubuntu",
            },
            proc=lambda _: (1000, f"/system.slice/{CODER.unit}"),
            get_uid=lambda _: 1000,
        )
