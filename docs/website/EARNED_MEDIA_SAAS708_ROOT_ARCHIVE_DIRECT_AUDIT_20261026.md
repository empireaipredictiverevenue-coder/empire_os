# Original ASTRA operator — direct protected archive audit

**Evidence, not an original-owner release authorisation.**

The root-owned protected directory and archive must have UID 0 and the exact 0700/0600 custody modes before any content audit is accepted.

The founder reported successful root creation of `/var/backups/empire-website/saas708-original-site-700-20261026.tar.gz`, SHA-256 `65f7d9ab99a3808ea4e18922ef662c94365a1511d4e62c0019f03f92bbf220c7`. A private archive with **exactly that SHA-256** was independently audited member-by-member against the live 700-file site. The direct privileged reading of the protected archive is still a separate original owner activity, because the unprivileged session cannot access the root-only directory.

For the original authorised website release operator to perform **one independent read-only direct member audit**, paste and review this self-contained Python snippet in its terminal. It neither extracts files nor writes a receipt. It does not execute user-writable development worktree code as root.

```bash
sudo /usr/bin/python3 - <<'PY'
from pathlib import Path, PurePosixPath
from hashlib import sha256
import json, stat, tarfile

live = Path("/srv/empire_os/apps/empire-public-site/out")
protected = Path("/var/backups/empire-website")
archive = protected / "saas708-original-site-700-20261026.tar.gz"
want_archive = "65f7d9ab99a3808ea4e18922ef662c94365a1511d4e62c0019f03f92bbf220c7"
want_source = "f6cb9f0f541b041ebd5ca397c3c87268d89a70e086e26a16c1d2534dc13315df"

assert not protected.is_symlink() and protected.is_dir()
assert protected.stat().st_uid == 0
assert stat.S_IMODE(protected.stat().st_mode) == 0o700
assert not archive.is_symlink() and archive.is_file()
assert archive.stat().st_uid == 0
assert stat.S_IMODE(archive.stat().st_mode) == 0o600

# Independently hash original live files, rejecting links and unsafe names.
baseline = {}
total_live = 0
assert live.is_dir() and not live.is_symlink()
for f in sorted(live.rglob("*")):
    assert not f.is_symlink()
    if f.is_dir():
        continue
    assert f.is_file()
    rel = f.relative_to(live).as_posix()
    assert rel not in baseline and not rel.startswith(".")
    assert ".." not in PurePosixPath(rel).parts
    size = f.stat().st_size
    assert size <= 20_000_000
    total_live += size
    assert total_live <= 120_000_000
    baseline[rel] = sha256(f.read_bytes()).hexdigest()
assert len(baseline) == 700
digest = sha256("".join(
    f"{name} {h}\n" for name, h in sorted(baseline.items())
).encode()).hexdigest()
assert digest == want_source

# Never unpack into production: only stream and hash archived regular files.
archived = {}
total_archived = 0
with tarfile.open(archive, "r:gz") as tar:
    for entry in tar:
        name = entry.name.removeprefix("./")
        pp = PurePosixPath(name)
        assert not pp.is_absolute() and ".." not in pp.parts
        if entry.isdir():
            continue
        assert entry.isfile() and name in baseline and name not in archived
        assert entry.size <= 20_000_000
        total_archived += entry.size
        assert total_archived <= 120_000_000
        stream = tar.extractfile(entry)
        assert stream is not None
        with stream:
            archived[name] = sha256(stream.read()).hexdigest()
assert archived == baseline
assert sha256(archive.read_bytes()).hexdigest() == want_archive
print(json.dumps({
    "status": "ROOT_ARCHIVE_700_MEMBERS_EXACT_AGAINST_LIVE",
    "root_owned_mode_0700_dir": True,
    "root_owned_mode_0600_archive": True,
    "source_inventory_sha256": digest,
    "archive_sha256": want_archive,
    "verified_regular_members": len(archived),
    "website_modified": False,
    "astra_owner_signoff_performed": False,
    "publication_performed": False
}, sort_keys=True))
PY
```

If it errors or current website hashes differ, STOP. An independent original-owner signoff is still required before any separate guarded website publisher; this command verifies backup integrity only.

The original 708-file founder review approval remains pinned to candidate `62b62b184d5597ffc806a825723c4638f2953702c823561233d30058e398dab2`, and the original owner must ensure that exact candidate is current. Do not use the old 672-file publisher.
