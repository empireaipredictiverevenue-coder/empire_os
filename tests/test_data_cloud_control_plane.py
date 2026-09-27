import pytest

from empire_os.data_cloud_control_plane import DataCloudProject, ProjectState


def test_public_api_cannot_be_enabled_without_approved_state():
    with pytest.raises(ValueError, match="approved"):
        DataCloudProject(
            project_id="p1",
            tenant_id="t1",
            state=ProjectState.READY_PRIVATE,
            public_api_enabled=True,
        ).validate()


def test_private_ready_project_is_valid():
    project = DataCloudProject(
        project_id="p1",
        tenant_id="t1",
        state=ProjectState.READY_PRIVATE,
    )
    assert project.as_dict()["public_api_enabled"] is False
