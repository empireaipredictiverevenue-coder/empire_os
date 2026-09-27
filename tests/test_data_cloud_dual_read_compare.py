import hashlib

from empire_os.data_cloud_dual_read_compare import _digest_primary_keys


def test_digest_primary_keys_is_sorted_and_newline_delimited() -> None:
    expected = hashlib.sha256(b"a\nb\n").hexdigest()
    assert _digest_primary_keys(["b", "a"]) == expected
