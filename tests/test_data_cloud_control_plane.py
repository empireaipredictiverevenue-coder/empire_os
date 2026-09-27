import pytest

from empire_os.data_cloud_control_plane import (
    DataCloudProject,
    ProjectState,
    transition_project,
)


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


def test_public_api_transition_requires_founder_approval():
    project = DataCloudProject("p1", "t1", ProjectState.READY_PRIVATE)
    with pytest.raises(PermissionError, match="founder approval"):
        transition_project(project, ProjectState.PUBLIC_API_APPROVED)


def test_founder_approved_public_transition_is_explicit():
    project = DataCloudProject("p1", "t1", ProjectState.READY_PRIVATE)
    public = transition_project(
        project,
        ProjectState.PUBLIC_API_APPROVED,
        founder_public_api_approved=True,
    )
    assert public.public_api_enabled is True
