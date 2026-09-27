from empire_os.data_cloud_api import api_registry_snapshot, default_api_registry


def test_all_api_surfaces_are_private_by_default():
    rows = default_api_registry()
    assert rows
    assert all(row.public_enabled is False for row in rows)


def test_no_raw_sql_surface_is_exposed():
    snapshot = api_registry_snapshot()
    assert snapshot["raw_sql_surface_count"] == 0
    assert snapshot["public_surface_count"] == 0


def test_data_surfaces_require_authentication():
    assert all(row.authenticated is True for row in default_api_registry())
