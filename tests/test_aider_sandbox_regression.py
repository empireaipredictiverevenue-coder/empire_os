from pathlib import Path

import empire_os.empire_coder_sandbox_runner as sandbox
from empire_os.empire_coder_sandbox_runner import _changed_paths


def test_sandbox_ignores_aider_repo_map_cache(tmp_path, monkeypatch):
    class Result:
        returncode = 0
        stdout = (
            "?? .aider.tags.cache.v4/aa/bb/cache.val\n"
            "?? empire_os/example.py\n"
        )
        stderr = ""

    monkeypatch.setattr(
        sandbox,
        "_run",
        lambda *args, **kwargs: Result(),
    )

    assert _changed_paths(tmp_path) == ["empire_os/example.py"]


def test_sandbox_initializes_optional_native_proposal():
    source = Path(sandbox.__file__).read_text(encoding="utf-8")
    assert "candidate = None\n        proposal = None" in source
    assert "if proposal is not None" in source
