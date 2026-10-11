"""Dry-run contract: never write the live commercial-loop snapshot."""
from unittest.mock import patch
from scripts import refresh_commercial_loop as module

def test_dry_run_never_writes_snapshot(capsys):
    with (patch.object(module, '_existing', return_value={}),
          patch.object(module, 'fetch_canonical_commercial_observations', return_value={}),
          patch.object(module, 'fetch_qualification_omega_inventory', return_value={}),
          patch.object(module, 'write_commercial_loop_snapshot') as writer):
        assert module.main(['--dry-run']) == 0
        writer.assert_not_called()
    assert 'highest_priority_blocker' in capsys.readouterr().out

def test_normal_refresh_still_writes(capsys):
    with (patch.object(module, '_existing', return_value={}),
          patch.object(module, 'fetch_canonical_commercial_observations', return_value={}),
          patch.object(module, 'fetch_qualification_omega_inventory', return_value={}),
          patch.object(module, 'write_commercial_loop_snapshot') as writer):
        assert module.main([]) == 0
        writer.assert_called_once()


def test_unavailable_gateway_dry_run_reports_failure_without_write(capsys):
    from empire_os.canonical_data_gateway import DataGatewayUnavailable
    with (patch.object(module, '_existing', return_value={}),
          patch.object(module, 'fetch_canonical_commercial_observations', side_effect=DataGatewayUnavailable('private credentials')),
          patch.object(module, 'write_commercial_loop_snapshot') as writer):
        assert module.main(['--dry-run']) == 2
        writer.assert_not_called()
    output = capsys.readouterr().out
    assert 'canonical_reader_unavailable' in output
    assert 'private credentials' not in output
