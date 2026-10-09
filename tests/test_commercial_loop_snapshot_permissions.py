import grp
import os
import stat
from empire_os.commercial_loop_observer import assess_commercial_loop, write_commercial_loop_snapshot


def test_snapshot_shared_only_with_trusted_ubuntu_group(tmp_path):
    target = tmp_path / 'commercial_loop.json'
    status = assess_commercial_loop({})
    write_commercial_loop_snapshot(status, target)
    info = target.stat()
    assert stat.S_IMODE(info.st_mode) == 0o640
    assert info.st_gid == grp.getgrnam('ubuntu').gr_gid
    assert not target.with_suffix('.json.tmp').exists()
    write_commercial_loop_snapshot(status, target)
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
