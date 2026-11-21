"""Add ONE authenticated, read-only Mautic inbox route to original Smart CRM.

Versioned root-owned additive release. The current document UI and every
preexisting CRM layer are imported intact; no duplicate app, auth, DB role,
secret, sender, webhook ingress, or contact mapping is created.

The new module(s) must be installed as exact hash-pinned 0644 root-owned
files in EXTENSION. Existing CRM auth remains the single authority.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import stat
import sys

ROOT = Path("/opt/empire-ai/crm-mautic-readonly-20261121-v3")
EXTENSION = ROOT / "empire_os"
PRIOR = Path("/opt/empire-ai/crm-documents-firstparty-20261121-v2")
PRIOR_ENTRY = PRIOR / "private_crm_documents_entrypoint_20261120.py"
PRIOR_SHA256 = "797ee750999ea01c133914f80829b4cf0228aea59addcfbdf5f055c8d27efbd0"
REVIEW = "/v1/revenue-crm/integrations/mautic/inbox/reviews"

# SHA256 pins injected by release build; never trust imports from mutable paths.
REVIEW_MODULE_SHA256 = "9fd7f8347acb955a7857a55a31c2747921d7234e94c35c797dc92153435d969f"
INBOX_MODULE_SHA256 = "a63e4f0d98a66cc8f91e2bfb9c9e2491b89209957fc948b7b4bd88ff504ce059"


def _root_owned_directory(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError("mautic_release_directory_not_immutable")


def _pinned(path: Path, digest: str) -> None:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != 0
        or info.st_mode & 0o022
        or hashlib.sha256(path.read_bytes()).hexdigest() != digest
    ):
        raise RuntimeError("mautic_release_source_mismatch")


def attach_same_private_crm() -> object:
    if Path(__file__).resolve() != ROOT / Path(__file__).name:
        raise RuntimeError("mautic_release_entrypoint_not_pinned")
    for folder in (ROOT, EXTENSION, PRIOR):
        _root_owned_directory(folder)
    _pinned(PRIOR_ENTRY, PRIOR_SHA256)
    _pinned(EXTENSION / "mautic_crm_review_api.py", REVIEW_MODULE_SHA256)
    _pinned(EXTENSION / "mautic_crm_inbox.py", INBOX_MODULE_SHA256)

    # Import original before appending a path, preserving ALL existing auth,
    # document UI, data-cloud, work queue and predictive routes in one app.
    sys.path.insert(0, str(PRIOR))
    import private_crm_documents_entrypoint_20261120 as original
    if Path(original.__file__).resolve() != PRIOR_ENTRY:
        raise RuntimeError("mautic_original_crm_entrypoint_mismatch")
    app = original.app
    if any(getattr(route, "path", None) == REVIEW for route in app.routes):
        raise RuntimeError("mautic_review_already_mounted")

    import empire_os
    if str(EXTENSION) in empire_os.__path__:
        raise RuntimeError("mautic_review_package_path_already_mounted")
    empire_os.__path__.append(str(EXTENSION))

    # Existing current CRM issuer+live membership+tenant-bound reader.
    # Never parse or grant based on an untrusted request identity.
    from crm_search_additive_20261109.entrypoint import resolver
    from empire_os.mautic_crm_review_api import create_mautic_crm_review_router

    # Current FastAPI uses lazy _IncludedRouter wrappers: app.routes is not
    # a flat route inventory. Verify the exact router BEFORE mounting, then
    # prove the resulting live HTTP contract in a separate process.
    router = create_mautic_crm_review_router(
        resolve_authenticated_read=resolver,
    )
    actual = {
        (method, route.path) for route in router.routes
        for method in getattr(route, "methods", set())
    }
    if actual != {("GET", REVIEW)}:
        raise RuntimeError("mautic_review_route_scope_mismatch")
    app.include_router(router)
    app.state.mautic_review_readonly_only = True
    return app


app = attach_same_private_crm()
