"""Reviewed status-reader correction on the exact existing Founder release.

No new API, route, service or credentials. Preserve the original pinned app,
all route dependencies and its source/auth ownership. Never edit that bundle.
"""
from hashlib import sha256
import importlib.util
from pathlib import Path
import sys

PARENT = Path('/opt/empire-ai/founder-read-releases/agentos-intelligence-20261112v1/api')
PARENT_MODULE = 'agentos_existing_founder_overlay'
PARENT_SHA = '3b55a4c9fa506a25e1ec7f8ae07963ec6170569b4b7315bea9189b80e472597e'
OLD_READER_SHA = '69c5824cb491bb2ff3c26c3b0b5351637987c50ff0b83732f4c156705915c863'
NEW_READER_SHA = 'fbdec3a4633445c820bac6ed738a79105a60c885bb6e3f2d474b5d6438c3205b'
ROUTE = '/v1/predictive-cloud/status'


def checked_bytes(path: Path, expected: str) -> None:
    if path.is_symlink() or not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('CLOUD_STATUS_RELEASE_SOURCE_PIN_HOLD')


checked_bytes(PARENT / (PARENT_MODULE + '.py'), PARENT_SHA)
sys.path.insert(0, str(PARENT))
parent = __import__(PARENT_MODULE)
app = parent.app
routes_included_by_app = parent.routes_included_by_app
before = routes_included_by_app()
if sum(before.values()) != 87 or before.get((ROUTE, ('GET',))) != 1:
    raise RuntimeError('CLOUD_STATUS_EXISTING_ROUTE_CONTRACT_HOLD')
if app.middleware_stack is not None:
    raise RuntimeError('CLOUD_STATUS_STARTUP_ONLY_PATCH_REQUIRED')

original = sys.modules.get('empire_os.predictive_cloud_status_api')
if original is None or not getattr(original, '__file__', None):
    raise RuntimeError('CLOUD_STATUS_ORIGINAL_READER_UNAVAILABLE')
checked_bytes(Path(original.__file__), OLD_READER_SHA)
source = Path(__file__).resolve().parent / 'predictive_cloud_status_api.py'
checked_bytes(source, NEW_READER_SHA)
spec = importlib.util.spec_from_file_location('empire_reviewed_cloud_status_reader', source)
if spec is None or spec.loader is None:
    raise RuntimeError('CLOUD_STATUS_REVIEWED_READER_IMPORT_HOLD')
reviewed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviewed)

# Keep the stronger frozen release's component attestation, public-field
# allowlist and outcome-audit projection. The new checks are additional;
# never replace that original trust decision with the repository's reader.
original_reader = original.read_predictive_cloud_status


def checked_original_status(path=original.DEFAULT_SNAPSHOT, *, now=None):
    checked = reviewed.read_predictive_cloud_status(path, now=now)
    if checked.get('available') is not True:
        return checked
    result = original_reader(path, now=now)
    if result.get('available') is True:
        result = {**result, 'snapshot_state': checked['snapshot_state']}
    return result


# The existing route resolves this original module global on every GET.
original.read_predictive_cloud_status = checked_original_status


@app.middleware('http')
async def protect_existing_cloud_status_cache(request, call_next):
    response = await call_next(request)
    if request.url.path == ROUTE:
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


if routes_included_by_app() != before:
    raise RuntimeError('CLOUD_STATUS_EXISTING_ROUTING_CHANGED')
