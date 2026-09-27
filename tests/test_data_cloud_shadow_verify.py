import hashlib
import json
from pathlib import Path

import pytest

from empire_os.data_cloud_shadow_copy import ShadowTable
from empire_os.data_cloud_shadow_verify import digest_primary_keys, load_expected


def test_digest_primary_keys_matches_sorted_newline_contract() -> None:
    expected = hashlib.sha256(b"a\nb\n").hexdigest()
    assert digest_primary_keys(["b", "a"]) == expected


def test_load_expected_requires_verified_complete_manifest(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps({
            "schema_version": "empire.shadow-dump-import.v1",
            "verified": True,
            "tables": [{
                "table": "example",
                "source_rows": 1,
                "source_pk_sha256": digest_primary_keys(["1"]),
                "verified": True,
            }],
        }),
        encoding="utf-8",
    )
    result = load_expected(report, (ShadowTable("example"),))
    assert result["example"]["source_rows"] == 1


def test_load_expected_rejects_manifest_drift(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps({
            "schema_version": "empire.shadow-dump-import.v1",
            "verified": True,
            "tables": [],
        }),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="manifest mismatch"):
        load_expected(report, (ShadowTable("example"),))
