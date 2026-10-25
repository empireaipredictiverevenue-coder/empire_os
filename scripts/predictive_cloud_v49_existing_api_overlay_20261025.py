"""Add one V4.9 read-only route to the EXACT currently pinned Founder API.

This wrapper does not import the full write-capable EmpireOS hub and does not
replace any existing Founder/Property/JEV router. It deliberately imports the
currently running composite_property_jev_overlay from its original release
directory and extends only the original empire_os package lookup for a
never-before-existing V4.9 read-only module under canonical /srv/empire_os.
"""
from __future__ import annotations

from pathlib import Path
import sys

ORIGINAL_PINNED_RELEASE = Path(
    "/home/ubuntu/empire_releases/property_birmingham_private_stage_20261022_v3"
)
CANONICAL_MODULES = Path("/srv/empire_os/empire_os")
ROUTE = "/v1/predictive-cloud/v4/shadow-readiness"

if not ORIGINAL_PINNED_RELEASE.is_dir() or not CANONICAL_MODULES.is_dir():
    raise RuntimeError("V49_EXISTING_API_OR_CANONICAL_REPO_UNAVAILABLE")

# Preserve pinned release priority (including its identity/auth, JEV and
# original read API). Do not substitute /srv for existing pinned modules.
sys.path.insert(0, str(ORIGINAL_PINNED_RELEASE))
from composite_property_jev_overlay import app
import empire_os

if str(CANONICAL_MODULES) not in empire_os.__path__:
    empire_os.__path__.append(str(CANONICAL_MODULES))

from empire_os.predictive_cloud_v49_readiness_api import (
    create_v49_shadow_readiness_router,
)

from collections import Counter

def routes_included_by_app():
    # FastAPI 2026 uses lazy _IncludedRouter wrappers, not flat APIRoutes.
    # Flatten only for accounting. Do not mutate the pinned source routers.
    def visit(items):
        for item in items:
            included = getattr(item, "original_router", None)
            if included is not None:
                yield from visit(included.routes)
            elif getattr(item, "path", None) is not None:
                yield (item.path, tuple(sorted(item.methods or ())))
            elif hasattr(item, "routes"):
                yield from visit(item.routes)
            else:
                raise RuntimeError("V49_UNKNOWN_EXISTING_ROUTE_TYPE")
    return Counter(visit(app.routes))

before = routes_included_by_app()
if any(path == ROUTE for path, methods in before):
    raise RuntimeError("V49_SHADOW_ROUTE_COLLISION")
app.include_router(create_v49_shadow_readiness_router())
after = routes_included_by_app()
expected = (ROUTE, ("GET",))
if after != before + Counter({expected: 1}):
    raise RuntimeError("V49_EXISTING_FOUNDER_ROUTING_CHANGED")
