import pytest

from empire_os.data_cloud_topology import DataNode, NodeRole, validate_topology


def test_topology_requires_exactly_one_primary():
    with pytest.raises(ValueError, match="exactly one primary"):
        validate_topology(
            (
                DataNode("a", NodeRole.PRIMARY, "eu", True, writable=True),
                DataNode("b", NodeRole.PRIMARY, "eu", True, writable=True),
            )
        )


def test_replica_cannot_be_writable():
    with pytest.raises(ValueError, match="replicas"):
        DataNode("r", NodeRole.SYNC_REPLICA, "eu", True, 0.1, True).validate()
