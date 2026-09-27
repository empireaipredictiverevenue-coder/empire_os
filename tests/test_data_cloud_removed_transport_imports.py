from pathlib import Path


def test_no_business_module_imports_removed_qualification_request_transport():
    root = Path(__file__).resolve().parents[1] / "empire_os"
    needle = "from empire_os.qualification_worker_v2 import request_json"
    offenders = []

    for path in sorted(root.rglob("*.py")):
        if needle in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(root.parent)))

    assert offenders == [], (
        "stale qualification-worker transport imports remain: "
        + ", ".join(offenders)
    )
