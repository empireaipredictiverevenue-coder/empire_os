"""Reproducible offline demo plugin archive; no WordPress installation or activation."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import json

REQUIRED = ('empire-car-yard.php', 'includes/class-empire-yard-booking-rules.php', 'includes/class-empire-yard-booking-store.php')


def package(source: Path, target: Path) -> dict:
    source, target = Path(source), Path(target)
    if target.exists():
        raise ValueError('Refuse overwrite of previous demo plugin archive')
    if source.is_symlink() or not source.is_dir():
        raise ValueError('Missing isolated plugin source')
    entries: list[tuple[str, bytes]] = []
    for rel in REQUIRED:
        path = source / rel
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000:
            raise ValueError('Unsafe WordPress plugin source: ' + rel)
        content = path.read_bytes()
        if not content.startswith(b'<?php'):
            raise ValueError('Invalid PHP plugin source')
        entries.append(('empire-car-yard/' + rel, content))
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target, 'x', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for filename, content in entries:
            info = ZipInfo(filename, date_time=(2026, 10, 22, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content, compress_type=ZIP_DEFLATED, compresslevel=9)
    return {
        'status': 'OFFLINE_CAR_YARD_PLUGIN_SOURCE_ONLY',
        'sha256': sha256(target.read_bytes()).hexdigest(),
        'bytes': target.stat().st_size,
        'files': len(entries),
        'live_wordpress_verified': False,
        'booking_persistence_implemented': False,
        'booking_store_source_staged': True,
        'database_schema_installed': False,
        'public_bookings_enabled': False,
        'production_changes': False,
    }


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    output = root / 'prototypes/agency_wordpress_service_handoff_20261022/dist/empire-car-yard-capability-demo-0.2.0.zip'
    print(json.dumps(package(root / 'prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard', output), sort_keys=True))
