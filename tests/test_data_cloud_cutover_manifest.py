from empire_os.data_cloud_cutover_manifest import build_cutover_manifest


def _green():
    return {
        "health": {
            "canonical_backend": "supabase_legacy",
            "candidate_runtime_healthy": True,
            "pitr_verified": True,
            "backup": {
                "healthy": True,
                "encrypted": True,
                "off_node_repository_verified": True,
            },
        },
        "rollback": {"rollback_ready": True},
        "runtime_canary": {"verified": True},
        "tenant": {"verified": True},
        "recovery": {"verified": True},
    }


def test_manifest_is_technically_ready_but_never_infers_founder_approval():
    g = _green()

    manifest = build_cutover_manifest(
        health=g["health"],
        rollback=g["rollback"],
        runtime_canary=g["runtime_canary"],
        tenant=g["tenant"],
        recovery=g["recovery"],
        founder_approved=False,
    )

    assert manifest["technical_ready_for_founder_approval"] is True
    assert manifest["canonical_cutover_approved"] is False
    assert manifest["production_cutover_ready"] is False
    assert manifest["production_cutover_authority"] is False
    assert manifest["founder_gate"]["status"] == "OPEN"


def test_manifest_fails_closed_when_off_node_backup_is_open():
    g = _green()
    g["health"]["backup"]["off_node_repository_verified"] = False
    g["health"]["pitr_verified"] = False

    manifest = build_cutover_manifest(
        health=g["health"],
        rollback=g["rollback"],
        runtime_canary=g["runtime_canary"],
        tenant=g["tenant"],
        recovery=g["recovery"],
    )

    gates = {row["name"]: row for row in manifest["technical_gates"]}
    assert gates["off_node_backup"]["status"] == "OPEN"
    assert gates["wal_pitr"]["status"] == "OPEN"
    assert manifest["technical_ready_for_founder_approval"] is False


def test_manifest_marks_missing_evidence_unknown():
    manifest = build_cutover_manifest(
        health={},
        rollback={},
        runtime_canary={},
        tenant={},
        recovery={},
    )

    assert all(
        row["status"] == "UNKNOWN"
        for row in manifest["technical_gates"]
    )
    assert manifest["technical_ready_for_founder_approval"] is False
    assert manifest["production_cutover_authority"] is False
