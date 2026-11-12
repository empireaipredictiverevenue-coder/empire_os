"""DesignOS fail-closed freeze of the existing VISUALLY REJECTED roofing page.

Matching this old release is continuity, NOT visual approval.
Unreviewed rebuilt HTML, RSC, JS or CSS fails closed. New visual release
requires separately founder-approved DesignOS acceptance and a guarded update.
"""
from hashlib import sha256
from pathlib import Path

FROZEN_ROOFING_DESIGN_STATE = "LEGACY_LIVE_VISUALLY_REJECTED"
FROZEN_ROOFING_RELEASE_DIGESTS = {
    '_next/static/chunks/1ed833f8-45e96d1e5d389f31.js': ('ab9f27b827dacdf6aa3863be4bdbd7fef0e85b00bf43482fd929a41035cbcbbd', 201054),
    '_next/static/chunks/60-75246e622966cbd8.js': ('67c8d8da534959b20ab68689fd2f1d10b78a327bc58c9addf62fa66479d3aaae', 241229),
    '_next/static/chunks/app/layout-ba2ee9faa8295536.js': ('5c8b2ce6972d8c0da0b71bedb7e0177a4c30419553fe100f22469ef3e244e51a', 3398),
    '_next/static/chunks/app/roofing/page-e32c4ec8a7bbd18a.js': ('dc6a3b801c0fe613582e5e6cdf616702cee80e7a7a7372d6418ee2546c3c44e7', 4847),
    '_next/static/chunks/main-app-87b5ca28e9619d8f.js': ('bb5f0794acc6899b8ea961bdad748d08a95321e7e0f5e9a0eaeb940354de2eed', 513),
    '_next/static/chunks/polyfills-42372ed130431b0a.js': ('0973c1d64c88adc8e3c950410cb58b288f72118d5965b78049438deb8f2f9683', 112594),
    '_next/static/chunks/webpack-86a453c728ce5eda.js': ('fb9b01c198149b1bdb3714c5048238e24cbb8666831a75bb5536801fcfb27fc8', 3547),
    '_next/static/css/5e9b4fb3fc416ab9.css': ('dd03f6832a8f29b88a164921aba1bf0c398ccdda25c39077e4a804197251834f', 124707),
    '_next/static/css/e3e4cc9c552c9bda.css': ('f4470199267c8dcfe9d6004eba00ee0e91b99c4b374b013efb236b91a80946b7', 11308),
    'roofing.html': ('39c59b1631feec8f6097e00534e2d4ac98c740523cbbc3717b0ff12305024683', 77007),
    'roofing.txt': ('ca4ae8126e83ed185ee1fb47151564cd9f55cd1536e6d6ec8709c7986d13a879', 40109),
    'roofing/__next._full.txt': ('ca4ae8126e83ed185ee1fb47151564cd9f55cd1536e6d6ec8709c7986d13a879', 40109),
    'roofing/__next.roofing.__PAGE__.txt': ('d62405aa29203b876881953e5c768fa09ae5a2bb8cddf2e21846625d5b166520', 39077),
}

def frozen_roofing_page_body(root: Path) -> bytes | None:
    """Return only independently SHA-checked legacy bytes; fail closed.

    The caller must serve these exact bytes, never re-open the HTML after
    validation. This prevents a changed candidate slipping into a
    response between the check and an asynchronous FileResponse.
    """
    try:
        base = Path(root).resolve(strict=True)
        body = None
        for name, (digest, size) in FROZEN_ROOFING_RELEASE_DIGESTS.items():
            p = base / name
            if (p.is_symlink() or not p.is_file()
                    or not p.resolve(strict=True).is_relative_to(base)
                    or p.stat().st_size != size):
                return None
            content = p.read_bytes()
            if len(content) != size or sha256(content).hexdigest() != digest:
                return None
            if name == "roofing.html":
                body = content
        return body
    except (OSError, ValueError, RuntimeError):
        return None


def current_roofing_export_frozen(root: Path) -> bool:
    """Legacy continuity only, NEVER DesignOS founder visual approval."""
    return frozen_roofing_page_body(root) is not None
