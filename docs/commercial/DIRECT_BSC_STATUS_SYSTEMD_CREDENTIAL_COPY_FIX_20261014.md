# Direct BSC checkout status — systemd credential copy fix (14 October 2026)

## Production incident

The guarded checkout buyer-status release returned:
```text
release_failure_stage=PRIVATE_STATUS_ROUTE_NOT_MOUNTED_ROLLBACK_OK
DIRECT_BSC_STATUS_MOUNT=HELD stage=credential_files
```
The release operator rolled back its newly installed systemd drop-in.
Both pre-existing checkout and gateway services were observed active.
The public /buy checkout page and pre-approved pending order gates
remained live, with payment execution and realised revenue still OFF.

## Narrow cause and correction

The root source files at
`/etc/empire_direct_bsc_buyer_status_hmac.key` and
`/etc/empire_direct_bsc_buyer_status.env` remain root:root mode **0600**.
systemd copies these using `LoadCredential` into its private per-unit
credential directory, and the delivered copy may be **0444**, unlike
the root-only source.

The existing status runtime incorrectly required mode 0600 on the
delivered copy, causing the `credential_files` fail-closed hold.

The fix in `empire_os/direct_bsc_buyer_checkout_release.py`:
- requires `CREDENTIALS_DIRECTORY` to match the exact
  `/run/credentials/empire-self-serve-checkout.service` directory;
- rejects a symlink or missing directory, or a directory with any
  permissions for unrelated users (mode & 0007);
- accepts the copied files only when regular, non-symlinked and
  **no write bit for anyone** (mode & 0222 = 0);
- preserves key-length, DSN-format, distinct-login, canonical local
  PostgreSQL, treasury, chain and minimum-confirmation checks;
- keeps the protected source files 0600 and never prints or rotates keys.

This follows the already-existing
`empire_os/tam_isolated_credential.py` approach for genuine systemd
credential copies. It is not a general relaxation of source-file access.

## Validation and activation scope

Tests cover a disposable exact checkout credential directory (0550),
delivered mode-0444 copies, wrong directory, directory world traversal,
symlink, writable file, and existing status/issuer regression.
No systemd restart, token issuance, payment or production file modification
occurred as part of this source fix.

The previously founder-approved guarded release command is still
`scripts.deploy_direct_bsc_buyer_status_release --apply
--approved-direct-bsc-buyer-status-release-only`. Only execute after
all code/tests are committed and readback confirms no 50 status drop-in.
If it fails, do not retry: inspect its redacted stage plus journal mount
stage and preserve the original key and buyer logins.

**This source fix alone does not claim the endpoint is now live**;
independent successful post-release route readback is still required.
