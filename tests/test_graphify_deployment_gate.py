


def test_immutable_private_graph_release_chain_with_real_source_receipts(tmp_path):
    """Use actual published code graph/receipts copied to an isolated directory.

    No fake buyers, fake revenue, model traffic or new Coder jobs.
    """
    import json
    from pathlib import Path
    ROOT = Path("/srv/empire_os")
    import shutil
    from hashlib import sha256

    from empire_os.graphify_deployment_gate import (
        GRAPH, MANIFEST, RELEASE, BACKUP, NEXT_RELEASE, NEXT_BACKUP,
        verify_release_custody,
    )

    files = (
        GRAPH, MANIFEST, RELEASE,
        BACKUP + "/graph.json", BACKUP + "/manifest.json",
    )
    for relative in files:
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o600)
    first = verify_release_custody(tmp_path)
    assert first["rollback_available"] is True
    assert first["release_generation"] == "ORIGINAL_ATTESTED_CODE"

    prior = json.loads((tmp_path / RELEASE).read_text())
    for old, filename in ((GRAPH, "graph.json"), (MANIFEST, "manifest.json")):
        target = tmp_path / NEXT_BACKUP / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tmp_path / old, target)
        target.chmod(0o600)

    # A byte-distinct code-graph generation is simulated only within
    # this temporary test directory. No production graph is touched.
    old_graph = (tmp_path / GRAPH).read_bytes()
    old_manifest = (tmp_path / MANIFEST).read_bytes()
    new_graph = old_graph + b"\n"
    new_manifest = old_manifest + b"\n"
    (tmp_path / GRAPH).write_bytes(new_graph)
    (tmp_path / MANIFEST).write_bytes(new_manifest)
    next_receipt = {
        "status": "LIVE_CURATED_REAL_SOURCE_EXPANSION_VERIFIED",
        "prior_graph_file_sha256": sha256(old_graph).hexdigest(),
        "prior_snapshot_file_sha256": sha256(old_manifest).hexdigest(),
        "current_graph_sha256": sha256(new_graph).hexdigest(),
        "current_manifest_sha256": sha256(new_manifest).hexdigest(),
    }
    target = tmp_path / NEXT_RELEASE
    target.write_text(json.dumps(next_receipt))
    target.chmod(0o600)
    newer = verify_release_custody(tmp_path)
    assert newer["rollback_available"] is True
    assert newer["release_generation"] == "IMPLEMENT_ADMISSION_REFRESH"

    next_receipt["prior_graph_file_sha256"] = "0" * 64
    target.write_text(json.dumps(next_receipt))
    invalid = verify_release_custody(tmp_path)
    assert invalid["rollback_available"] is False
    assert invalid["status"] == "DEPLOYMENT_HOLD"
