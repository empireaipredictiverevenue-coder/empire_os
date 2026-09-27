from empire_os.data_cloud_reliability import (
    BackupState,
    evaluate_reliability,
)
from empire_os.data_cloud_topology import DataNode, NodeRole


def _nodes():
    return (
        DataNode("db-1", NodeRole.PRIMARY, "eu-west", True, writable=True),
        DataNode("db-2", NodeRole.SYNC_REPLICA, "eu-west", True, 0.5),
        DataNode("db-3", NodeRole.DR_REPLICA, "eu-north", True, 5.0),
    )


def test_healthy_topology_requires_restore_and_pitr_proof():
    result = evaluate_reliability(
        _nodes(),
        BackupState(30.0, True, True, True, True),
    )
    assert result["healthy"] is True
    assert result["findings"] == []


def test_missing_restore_proof_is_not_healthy():
    result = evaluate_reliability(
        _nodes(),
        BackupState(30.0, True, True, False, True),
    )
    assert result["healthy"] is False
    assert "restore_not_verified" in result["findings"]


def test_reliability_evaluator_never_grants_destructive_authority():
    result = evaluate_reliability(
        _nodes(),
        BackupState(30.0, True, True, True, True),
    )
    assert result["authority"]["destructive_repair"] is False
    assert result["authority"]["automatic_failover_execution"] is False
